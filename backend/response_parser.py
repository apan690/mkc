"""
response_parser.py

Parses the LLM's raw text output (fixed format enforced by prompt_builder.py)
into structured Finding objects that both the WebSocket broadcaster and the
report generator can consume.

Expected line format:
[SEVERITY] FILE:LINE — Issue description. Fix: recommended fix.
"""

import re
from dataclasses import dataclass
from typing import List

# Tolerant header matcher: brackets around severity are optional, the
# separator between location and description can be an em-dash, hyphen,
# or colon. Smaller quantized models drift from the exact requested format
# fairly often, so this only requires the parts we actually need (severity,
# file, line, description) and treats everything else as best-effort.
FINDING_RE = re.compile(
    r"^\[?(CRITICAL|WARNING|SUGGESTION)\]?\s*[-:]?\s*"  # severity, optional brackets
    r"([^\s:]+):(\d+)"                                    # file:line
    r"\s*[—\-:]\s*"                                       # separator
    r"(.+)$",                                              # rest of line (description [+ fix])
    re.IGNORECASE,
)

# Looks for a "Fix:" style marker anywhere in the description tail, with
# common phrasing variants a model might use instead of the exact word "Fix:".
FIX_SPLIT_RE = re.compile(
    r"\s*(?:Fix|Recommended fix|Suggested fix)\s*(?:is)?\s*[:\-]?\s+",
    re.IGNORECASE,
)


@dataclass
class Finding:
    severity: str
    file: str
    line: int
    description: str
    fix: str = ""


def _strip_code_blocks(text: str) -> str:
    """Removes fenced ``` code blocks so they don't pollute line-by-line parsing."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def parse_findings(raw_output: str) -> List[Finding]:
    """
    Parses raw LLM text output into a list of Finding objects.

    Deliberately tolerant: the requested format is strict, but small
    quantized models drift from it (missing brackets, "Recommended fix"
    instead of "Fix:", occasional code blocks). This only requires enough
    structure to reliably locate severity + file + line, and takes a
    best-effort pass at splitting off the fix suggestion. Only the first
    line of a multi-line finding is captured — if a model wraps a finding
    across multiple lines, everything after the first line is dropped
    rather than causing a parse failure.
    """
    findings: List[Finding] = []

    if "NO_ISSUES_FOUND" in raw_output:
        return findings

    cleaned = _strip_code_blocks(raw_output)

    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue

        match = FINDING_RE.match(line)
        if not match:
            continue  # skip malformed/non-finding lines rather than raising

        severity, file_path, line_no, rest = match.groups()

        fix = ""
        fix_split = FIX_SPLIT_RE.split(rest, maxsplit=1)
        description = fix_split[0].strip()
        if len(fix_split) > 1:
            fix = fix_split[1].strip()

        findings.append(
            Finding(
                severity=severity.upper(),
                file=file_path,
                line=int(line_no),
                description=description,
                fix=fix,
            )
        )

    return findings


if __name__ == "__main__":
    sample_output = """[CRITICAL] auth.py:42 — SQL injection vulnerability. Fix: Use parameterized queries instead of string formatting.
[WARNING] utils.py:17 — Unused import 'os'. Fix: Remove the unused import.
some stray line the model shouldn't have written
[SUGGESTION] helpers.py:55 — Consider extracting to separate function."""

    for f in parse_findings(sample_output):
        print(f)
