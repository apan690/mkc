# DevMesh — Privacy-First On-Device AI Code Review Agent

> Skeleton / pre-orientation build. See `PROJECT_KNOWLEDGE.md` (not in repo, kept
> separately) for full architecture and rationale.

## What this is (current state)

A working local pipeline that:
1. Reads a git diff (last commit or staged changes)
2. Splits it into per-hunk pieces with full function context
3. Sends each hunk to a local LLM (Phi-3 Mini via Ollama) for review
4. Parses the model's output into structured findings
5. Fans out findings to two stub destinations (mobile broadcaster stub,
   plain-text report stub) — these will be replaced by the real WebSocket
   server + mobile app and the real Jinja2/PDF report before Phase 2.

## Setup

1. Install [Ollama](https://ollama.com)
2. Pull the model: `ollama pull phi3`
3. Start the Ollama server (usually auto-starts, or run `ollama serve`)
4. Install Python deps: `pip install -r backend/requirements.txt`

## Run

From inside a git repo with at least one commit:

```bash
cd backend
python run_review.py
```

See `HOW_TO_RUN.md` for a full step-by-step walkthrough including how to test
against the sample buggy files in `samples/`.

## Team

- Hardik (Team Lead) — LLM integration, prompt engineering, response parsing, WebSocket server, repo management
- Vatsal — React Native mobile app, WebSocket client, report template
- Dhruv — Git hook script, GitHub webhook listener, FastAPI server

## License

MIT (see LICENSE)
