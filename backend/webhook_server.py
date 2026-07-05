"""
webhook_server.py

FastAPI listener for the GitHub PR trigger path (Section 3/6 of the
knowledge file: "GitHub PR submission -> via local webhook listener").

SCOPE (per Section 12 skeleton): real GitHub payload parsing / fetching the
actual PR diff from GitHub's API is deliberately NOT built yet. This
accepts a real or mock `pull_request` webhook payload, validates it looks
like one, and then reviews the CURRENT LOCAL REPO's diff (same as the
post-commit hook path) as a stand-in for "the PR's diff." Swap the diff
source once real PR-diff fetching is wired up post-orientation.

WHY IMPORT DIRECTLY INSTEAD OF SHELLING OUT TO run_review.py:
run_review.py's main() does argparse + ends with a blocking input() (a
keep-alive so the WebSocket doesn't die immediately when run manually).
Shelling out to it as a subprocess means fighting that blocking call and
losing easy access to results. Importing diff_extractor / prompt_builder /
llm_client / response_parser / ws_broadcaster / report_generator directly
(same as run_review.py does) gives the same pipeline without either
problem, and requires zero changes to Hardik's or Vatsal's modules.

RUN STANDALONE:
    cd backend
    uvicorn webhook_server:app --reload --port 8000
(port 8000 chosen to avoid colliding with ws_broadcaster's 8765)

TEST IT (mock PR payload, no real GitHub needed):
    curl -X POST http://localhost:8000/webhook \
      -H "X-GitHub-Event: pull_request" \
      -H "Content-Type: application/json" \
      -d '{"action": "opened", "pull_request": {"number": 1}}'
"""

import time
import traceback
from collections import defaultdict
from typing import Optional

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from diff_extractor import get_last_commit_diff, get_diff, split_into_hunks
from prompt_builder import build_prompt
from llm_client import review_hunk
from response_parser import parse_findings
from ws_broadcaster import broadcast_findings  # importing this also starts the WS server eagerly (see ws_broadcaster.py)
from report_generator import generate_report

app = FastAPI(title="DevMesh Webhook Listener")


def run_pipeline_for_repo(repo_path: str = ".", staged: bool = False) -> dict:
    """
    Same core loop as run_review.py's main(), pulled out as a reusable
    function so both the CLI entrypoint and this webhook can share it
    without either one blocking on argparse or input().

    Returns a small summary dict instead of printing to stdout only,
    since a webhook caller may want to know what happened.
    """
    if staged:
        raw_diff = get_diff(repo_path, staged=True)
    else:
        raw_diff = get_last_commit_diff(repo_path)

    hunks = split_into_hunks(raw_diff)

    if not hunks:
        return {"hunks_reviewed": 0, "findings_total": 0, "report_path": None}

    all_findings = defaultdict(list)
    total_latency = 0.0

    for hunk in hunks:
        prompt = build_prompt(hunk)
        start = time.time()
        result = review_hunk(prompt)
        total_latency += time.time() - start

        findings = parse_findings(result.raw_output)
        all_findings[hunk.file_path].extend(findings)

    for file_path, findings in all_findings.items():
        if findings:
            broadcast_findings(findings, file_path)

    report_path = generate_report(dict(all_findings))

    findings_total = sum(len(v) for v in all_findings.values())
    return {
        "hunks_reviewed": len(hunks),
        "findings_total": findings_total,
        "total_latency_seconds": round(total_latency, 2),
        "report_path": report_path,
    }


def _looks_like_pull_request_payload(payload: dict) -> bool:
    """
    Loose validation only — real GitHub webhook payloads always include
    a top-level "pull_request" object and an "action" field, but since
    we're explicitly supporting mock payloads for now (Section 12), this
    just checks for the "pull_request" key rather than doing full schema
    validation against GitHub's actual webhook shape.
    """
    return isinstance(payload, dict) and "pull_request" in payload


@app.get("/health")
async def health():
    """Quick sanity check — hit this first to confirm the server is up."""
    return {"status": "ok", "service": "devmesh-webhook-listener"}


@app.post("/webhook")
async def webhook(request: Request, x_github_event: Optional[str] = Header(default=None)):
    """
    Receives a GitHub PR webhook (or a mock payload shaped like one) and
    triggers a DevMesh review.

    NOTE: this reviews the current local repo's last commit as a stand-in
    for the actual PR diff (see module docstring) — real PR-diff fetching
    from GitHub's API is a post-orientation task, not done here.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # GitHub sets this header on every webhook delivery. Mock/manual test
    # calls may not set it, so we don't hard-fail if it's missing — we
    # just prefer it as the primary signal when present.
    event_type = (x_github_event or payload.get("event_type") or "").lower()

    if event_type and event_type != "pull_request":
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": f"event type '{event_type}' is not pull_request"},
        )

    if not event_type and not _looks_like_pull_request_payload(payload):
        return JSONResponse(
            status_code=400,
            content={
                "status": "rejected",
                "reason": "Payload doesn't look like a pull_request event "
                "(missing X-GitHub-Event header and no 'pull_request' key in body).",
            },
        )

    pr_number = None
    if isinstance(payload.get("pull_request"), dict):
        pr_number = payload["pull_request"].get("number")

    print(f"[webhook_server] Received pull_request event (PR #{pr_number}). Running review...")

    try:
        summary = run_pipeline_for_repo()
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "reason": str(e)},
        )

    print(f"[webhook_server] Review complete: {summary}")
    return {"status": "reviewed", "pr_number": pr_number, **summary}


if __name__ == "__main__":
    # Convenience for `python webhook_server.py` — prefer running via
    # uvicorn directly for --reload during development though.
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
