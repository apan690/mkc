"""
ws_broadcaster.py

STUB VERSION — Section 12 skeleton milestone.

This is a placeholder for the real WebSocket server that will stream findings
to the React Native mobile app (Vatsal's piece). For now it just prints what
WOULD be sent, so the pipeline's fan-out SHAPE exists end-to-end before the
real WebSocket server and mobile client are wired up.

Swap this out once ws_broadcaster (real) + the mobile WebSocket client exist —
keep the function signature (`broadcast_findings`) identical so run_review.py
doesn't need to change.
"""

import json
from typing import List
from response_parser import Finding


def broadcast_findings(findings: List[Finding], file_path: str) -> None:
    """
    STUB: prints the payload that would be sent over WebSocket to the mobile
    triage UI. Real version (Dhruv/Hardik) will open a WS connection and push
    this as JSON to connected clients.
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
    print("[ws_broadcaster STUB] Would send to mobile app:")
    print(json.dumps(payload, indent=2))
