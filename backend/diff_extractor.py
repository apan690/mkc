"""
diff_extractor.py

Extracts diff hunks from a git repo using --function-context so each hunk
carries the full enclosing function, not just +/- 3 lines of default context.

SKELETON VERSION (pre-orientation):
- No chunking yet (Section 7 chunking fallback deferred to Phase C).
- Assumes every hunk fits in the model's context window.
- One call per hunk downstream (this module just does the splitting).
"""

import subprocess
import re
from dataclasses import dataclass
from typing import List


@dataclass
class Hunk:
    file_path: str
    start_line: int
    diff_text: str


def get_diff(repo_path: str = ".", staged: bool = True) -> str:
    """
    Returns the raw git diff with full function context.

    staged=True  -> git diff --cached --function-context   (post-commit style: compares last commit)
    staged=False -> git diff --function-context             (unstaged working tree changes)
    """
    cmd = ["git", "-C", repo_path, "diff"]
    if staged:
        cmd.append("--cached")
    cmd.append("--function-context")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr}")
    return result.stdout


def get_last_commit_diff(repo_path: str = ".") -> str:
    """
    For the post-commit hook use case: diff of the most recent commit
    against its parent, with function context.
    """
    cmd = ["git", "-C", repo_path, "diff", "HEAD~1", "HEAD", "--function-context"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Likely the very first commit (no HEAD~1) — fall back to full diff of that commit
        cmd = ["git", "-C", repo_path, "show", "HEAD", "--function-context"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"git diff/show failed: {result.stderr}")
    return result.stdout


def split_into_hunks(raw_diff: str) -> List[Hunk]:
    """
    Splits a unified diff into per-file, per-hunk chunks.
    Each Hunk.diff_text is self-contained enough to send as one LLM call.

    No chunking of oversized hunks here (skeleton). That's a Phase C addition
    once MAX_HUNK_TOKENS is confirmed post-orientation.
    """
    hunks: List[Hunk] = []
    current_file = None
    current_hunk_lines: List[str] = []
    current_start_line = 0

    file_header_re = re.compile(r"^\+\+\+ b/(.+)$")
    hunk_header_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    def flush():
        if current_file and current_hunk_lines:
            hunks.append(
                Hunk(
                    file_path=current_file,
                    start_line=current_start_line,
                    diff_text="\n".join(current_hunk_lines),
                )
            )

    for line in raw_diff.splitlines():
        file_match = file_header_re.match(line)
        if file_match:
            flush()
            current_file = file_match.group(1)
            current_hunk_lines = []
            continue

        hunk_match = hunk_header_re.match(line)
        if hunk_match:
            flush()
            current_start_line = int(hunk_match.group(1))
            current_hunk_lines = [line]
            continue

        if current_hunk_lines:
            current_hunk_lines.append(line)

    flush()
    return hunks


if __name__ == "__main__":
    # Manual smoke test: run from inside a git repo with a commit already made
    diff = get_last_commit_diff(".")
    hunks = split_into_hunks(diff)
    print(f"Found {len(hunks)} hunk(s)")
    for h in hunks:
        print(f"--- {h.file_path} @ line {h.start_line} ---")
        print(h.diff_text[:300])
        print()
