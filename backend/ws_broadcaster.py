"""
ws_broadcaster.py

REAL VERSION (minimal, scoped for tonight's end-to-end test only).

Drop-in replacement for the print-only stub. Function signature is
UNCHANGED — broadcast_findings(findings, file_path) — so run_review.py
does not need any edits.

WHAT THIS DOES:
- The first time broadcast_findings() is called, it lazily starts a real
  WebSocket server (ws://0.0.0.0:8765) in a background thread, since
  run_review.py itself runs synchronously top-to-bottom and can't also
  run an asyncio event loop on the main thread without being restructured.
- Every call after that pushes the same JSON payload shape as before to
  any currently connected clients (e.g. the DevMesh mobile app).

DELIBERATE SCOPE LIMITS (read before relying on this beyond tonight):
1. The server only lives as long as this run_review.py PROCESS is running.
   Once run_review.py finishes (after the last hunk + report write), the
   process exits and the mobile app will see a disconnect. Fine for a
   single test run tonight; not fine for a real git-hook-triggered
   pipeline where mobile should stay connected across many commits.
2. NO backlog/replay: if the mobile app connects AFTER a finding was
   already broadcast, it will simply miss it. For tonight's test: start
   the mobile app FIRST, confirm it shows "Live", THEN run run_review.py.
3. NO reconnection handling beyond what the `websockets` library gives us
   for free (client dropping is handled; server crash is not).
4. Local network only (ws://, not wss://) — fine for same-WiFi testing,
   not for anything beyond this LAN.

These limits are intentional trade-offs to get a real end-to-end test
working tonight without redesigning run_review.py. A persistent,
long-running broadcaster (its own process, decoupled from any single
review run) is the right shape before Phase 2 — revisit post-orientation.
"""

import asyncio
import json
import threading
from typing import List
from response_parser import Finding

HOST = "0.0.0.0"
PORT = 8765
SERVER_START_TIMEOUT_SECONDS = 5

_loop = None
_server_started = threading.Event()
_connected_clients = set()
_server_thread_lock = threading.Lock()
_server_thread_launched = False


def _start_server_thread():
    """
    Runs a dedicated asyncio event loop + websockets server in a background
    daemon thread, so the rest of run_review.py's synchronous code does not
    need to change at all. Safe to call more than once (e.g. once eagerly
    at import time and once explicitly from main()) — only the first call
    actually launches the thread; later calls are no-ops.
    """
    global _loop, _server_thread_launched

    with _server_thread_lock:
        if _server_thread_launched:
            return
        _server_thread_launched = True

    async def handler(websocket):
        _connected_clients.add(websocket)
        print(f"[ws_broadcaster] Mobile client connected: {websocket.remote_address}")
        try:
            await websocket.wait_closed()
        finally:
            _connected_clients.discard(websocket)
            print("[ws_broadcaster] Mobile client disconnected.")

    async def serve_forever():
        import websockets
        async with websockets.serve(handler, HOST, PORT):
            print(f"[ws_broadcaster] WebSocket server listening on ws://{HOST}:{PORT}")
            _server_started.set()
            await asyncio.Future()  # run until process exits

    def run_loop():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _loop.run_until_complete(serve_forever())

    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()

    # Block briefly so the very first broadcast_findings() call doesn't
    # race the server startup (e.g. first hunk finishing before the
    # background thread has finished binding the socket).
    if not _server_started.wait(timeout=SERVER_START_TIMEOUT_SECONDS):
        print(
            "[ws_broadcaster] WARNING: server did not confirm startup within "
            f"{SERVER_START_TIMEOUT_SECONDS}s — findings may not be delivered."
        )


def broadcast_findings(findings: List[Finding], file_path: str) -> None:
    """
    SAME SIGNATURE AS THE STUB. run_review.py calls this exactly as before.

    First call: lazily starts the WebSocket server (see above).
    Every call: builds the same payload dict the original stub built, and
    pushes it as JSON to any mobile clients connected right now.
    """
    payload = {
        "file": file_path,
        "findings": [
            {
                "severity": f.severity,
                "line": f.line,
                "description": f.description,
                "fix": f.fix,
            }
            for f in findings
        ],
    }
    message = json.dumps(payload)

    if not _connected_clients:
        print("[ws_broadcaster] No mobile client connected — message NOT delivered:")
        print(message)
        return

    async def _send_to_all():
        # gather() so one slow/dead client can't block delivery to others
        await asyncio.gather(
            *[client.send(message) for client in list(_connected_clients)],
            return_exceptions=True,
        )

    asyncio.run_coroutine_threadsafe(_send_to_all(), _loop)
    print(f"[ws_broadcaster] Sent to {len(_connected_clients)} client(s):")
    print(message)


# Start the server the moment this module is imported (i.e. as soon as
# run_review.py's `from ws_broadcaster import broadcast_findings` line
# runs) rather than waiting for the first finding. This is the fix for the
# original bug: with a lazy start, the server wasn't listening until AFTER
# the first hunk finished its LLM call (20-40s), so a mobile app that
# connected before running run_review.py would fail to connect and never
# retry. Starting eagerly here means the server is already listening
# before any hunk is even extracted.
_start_server_thread()