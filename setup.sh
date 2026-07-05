#!/bin/bash
#
# setup.sh
#
# One-command setup for DevMesh on a clean clone.
#
# WHAT THIS DOES:
#   1. Installs Python dependencies (backend/requirements.txt)
#   2. Installs the post-commit git hook (hooks/post-commit -> .git/hooks/post-commit)
#   3. Starts the FastAPI webhook listener in the background (port 8000)
#
# WHAT THIS DELIBERATELY DOES NOT DO:
#   Start the WebSocket broadcaster as a separate step. It doesn't need
#   to be — ws_broadcaster.py starts its server (ws://0.0.0.0:8765)
#   automatically the moment it's imported, which happens as soon as
#   either run_review.py (via a commit) or webhook_server.py (via this
#   script) runs. Starting it a third time here would just be a wasted,
#   redundant no-op at best (Vatsal's _start_server_thread() is
#   idempotent) — but running two full run_review.py processes
#   simultaneously is NOT safe, so this script is careful not to do that.
#
# USAGE:
#   ./setup.sh
#
# Run from the repo root (the folder containing backend/, hooks/, samples/, etc).
#
# NOTE: deliberately NOT using `set -e` here. A pip hiccup (e.g. a
# system-managed Python refusing global installs, a flaky network) is not
# a reason to also skip installing the git hook — that's the step most
# worth getting right even if deps need a manual follow-up. Each step
# below checks its own result and reports clearly instead.

set +e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== DevMesh Setup ==="
echo

# --- 0. Sanity checks -------------------------------------------------
if [ ! -d "backend" ]; then
    echo "ERROR: backend/ not found. Run this script from the repo root."
    exit 1
fi

if [ ! -d ".git" ]; then
    echo "WARNING: .git not found — this doesn't look like a git repo yet."
    echo "The post-commit hook install step will be skipped."
    IS_GIT_REPO=0
else
    IS_GIT_REPO=1
fi

# --- 1. Install Python dependencies ------------------------------------
echo "[1/3] Installing Python dependencies from backend/requirements.txt..."
if command -v pip3 &> /dev/null; then
    PIP_CMD=pip3
else
    PIP_CMD=pip
fi
if $PIP_CMD install -r backend/requirements.txt; then
    echo "      Done."
else
    echo "      WARNING: pip install failed (see above). Continuing with hook"
    echo "      install anyway — you may need to install deps manually, e.g.:"
    echo "        $PIP_CMD install -r backend/requirements.txt --break-system-packages"
    echo "      or from a virtualenv."
fi
echo

# --- 2. Install the post-commit hook -----------------------------------
if [ "$IS_GIT_REPO" -eq 1 ]; then
    echo "[2/3] Installing post-commit git hook..."
    if [ ! -f "hooks/post-commit" ]; then
        echo "      WARNING: hooks/post-commit not found — skipping hook install."
    else
        cp hooks/post-commit .git/hooks/post-commit
        chmod +x .git/hooks/post-commit
        echo "      Installed to .git/hooks/post-commit (and made executable)."
    fi
else
    echo "[2/3] Skipped (not a git repo)."
fi
echo

# --- 3. Start the webhook listener --------------------------------------
echo "[3/3] Starting FastAPI webhook listener on port 8000..."
cd backend

# Guard against double-starting the listener if setup.sh is re-run while
# a previous instance is still alive. Using curl against /health rather
# than lsof, since lsof isn't reliably available on every teammate's
# machine (notably Windows/Git Bash), while curl already is (used below
# in the "next steps" output too).
if curl -s -o /dev/null -m 2 http://localhost:8000/health; then
    echo "      Something is already listening on port 8000 (health check"
    echo "      responded) — leaving it running, not starting a second instance."
else
    nohup uvicorn webhook_server:app --host 0.0.0.0 --port 8000 > /tmp/devmesh_webhook.log 2>&1 &
    sleep 1
    echo "      Started (PID $!). Logs: /tmp/devmesh_webhook.log"
fi

cd "$SCRIPT_DIR"
echo

# --- Done ----------------------------------------------------------------
echo "=== Setup complete ==="
echo
echo "Next steps:"
echo "  - Make a commit (e.g. against a file in samples/) to trigger a review"
echo "    automatically via the post-commit hook."
echo "  - Or simulate a GitHub PR event:"
echo "      curl -X POST http://localhost:8000/webhook \\"
echo "        -H \"X-GitHub-Event: pull_request\" \\"
echo "        -H \"Content-Type: application/json\" \\"
echo "        -d '{\"action\": \"opened\", \"pull_request\": {\"number\": 1}}'"
echo "  - Check webhook listener health: curl http://localhost:8000/health"
echo "  - Findings stream over ws://0.0.0.0:8765 to the mobile app (if running),"
echo "    and a plain-text report is written to backend/devmesh_report.txt."
echo
