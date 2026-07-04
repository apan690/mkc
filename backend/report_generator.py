"""
report_generator.py

STUB VERSION — Section 12 skeleton milestone.

Placeholder for the real Jinja2 + WeasyPrint HTML/PDF report (Vatsal/Dhruv's
piece, Section 5 tech stack). For now this writes a plain text report to disk
so the pipeline's second fan-out branch exists end-to-end.

Swap this out once templates/report.html.j2 exists — keep the function
signature (`generate_report`) identical so run_review.py doesn't need to change.
"""

import os
from datetime import datetime
from typing import List, Dict

SEVERITY_ICONS = {
    "CRITICAL": "\U0001F534",
    "WARNING": "\U0001F7E1",
    "SUGGESTION": "\U0001F7E2",
}


def generate_report(all_findings: Dict[str, list], output_path: str = "devmesh_report.txt") -> str:
    """
    STUB: writes a plain text report grouped by file.
    all_findings: dict mapping file_path -> List[Finding]
    Returns the path to the written report.
    """
    lines = []
    lines.append(f"DevMesh Review Report — {datetime.now().strftime('%B %d, %Y %H:%M')}")
    lines.append("")

    total = sum(len(v) for v in all_findings.values())
    if total == 0:
        lines.append("No issues found. Clean diff!")
    else:
        for file_path, findings in all_findings.items():
            if not findings:
                continue
            lines.append(f"--- {file_path} ---")
            for f in findings:
                icon = SEVERITY_ICONS.get(f.severity, "-")
                lines.append(f"  {icon} [{f.severity}] line {f.line}: {f.description}")
                if f.fix:
                    lines.append(f"      Fix: {f.fix}")
            lines.append("")

    report_text = "\n".join(lines)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(report_text)

    return os.path.abspath(output_path)
