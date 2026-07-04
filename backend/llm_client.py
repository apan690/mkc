"""
llm_client.py

Thin wrapper around the local LLM backend.

SKELETON VERSION: talks to Ollama (localhost) running Phi-3 Mini.
Post-orientation: swap the internals of `review_hunk()` to call Qualcomm AI Hub
running on the Snapdragon NPU instead. Keep the function signature identical
so nothing else in the pipeline needs to change.
"""

import os
import time
import requests
from dataclasses import dataclass

OLLAMA_URL = "http://localhost:11434/api/generate"
# Override with: set DEVMESH_MODEL=phi3:mini  (or whatever `ollama list` shows locally)
MODEL_NAME = os.environ.get("DEVMESH_MODEL", "phi3:mini")

# Set via env var DEVMESH_MOCK_LLM=1 to bypass Ollama entirely and return a
# canned response. Useful for testing the rest of the pipeline (diff
# extraction, parsing, fan-out) while Ollama/CUDA issues are debugged separately.
MOCK_MODE = os.environ.get("DEVMESH_MOCK_LLM", "0") == "1"

MOCK_RESPONSE = """[CRITICAL] file.py:1 — Mocked finding: potential SQL injection. Fix: use parameterized queries.
[WARNING] file.py:2 — Mocked finding: unused variable. Fix: remove it.
[SUGGESTION] file.py:3 — Mocked finding: consider extracting this to a helper function."""


@dataclass
class LLMResult:
    raw_output: str
    latency_seconds: float


# Default timeout is generous because CPU-only inference on larger diffs
# (or the first call after Ollama starts, which includes model load time)
# can take well over a minute. Override with: set DEVMESH_TIMEOUT=600
DEFAULT_TIMEOUT = int(os.environ.get("DEVMESH_TIMEOUT", "300"))


def review_hunk(prompt: str, model: str = MODEL_NAME, timeout: int = DEFAULT_TIMEOUT) -> LLMResult:
    """
    Sends a single prompt to the local Ollama server and returns the raw
    text output plus latency (for the benchmark harness — Section 9 of the
    knowledge file wants single-call vs chunked latency logged separately).

    If MOCK_MODE is on (DEVMESH_MOCK_LLM=1), skips Ollama entirely and
    returns a canned response instantly, so the rest of the pipeline can be
    tested independently of the LLM backend being available.
    """
    if MOCK_MODE:
        time.sleep(0.1)  # simulate a bit of latency for realistic timing logs
        return LLMResult(raw_output=MOCK_RESPONSE, latency_seconds=0.1)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    start = time.time()
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(
            "Could not reach Ollama at http://localhost:11434. "
            "Is Ollama running? Try `ollama serve` in another terminal."
        ) from e
    except requests.exceptions.HTTPError as e:
        # Surface Ollama's actual error body instead of just the status code.
        # Common cause: model name doesn't match what's pulled (check `ollama list`).
        try:
            error_detail = response.json().get("error", response.text)
        except ValueError:
            error_detail = response.text
        raise RuntimeError(
            f"Ollama returned {response.status_code} for model '{model}': {error_detail}\n"
            f"Run `ollama list` to confirm the exact model name you have pulled."
        ) from e
    elapsed = time.time() - start

    data = response.json()
    return LLMResult(raw_output=data.get("response", ""), latency_seconds=elapsed)


if __name__ == "__main__":
    # Manual smoke test — requires `ollama serve` running and `ollama pull phi3` done
    test_prompt = (
        "You are a senior code reviewer. Analyze the following git diff and "
        "identify issues.\n\nFor each issue respond ONLY in this exact format:\n"
        "[SEVERITY] FILE:LINE — Issue description. Fix: recommended fix.\n\n"
        "SEVERITY must be one of: CRITICAL, WARNING, SUGGESTION\n"
        "Do not explain. Do not add preamble.\n\n"
        'Git diff:\n+    query = "SELECT * FROM users WHERE id = " + user_id\n'
    )
    result = review_hunk(test_prompt)
    print(f"Latency: {result.latency_seconds:.2f}s")
    print("Output:")
    print(result.raw_output)
