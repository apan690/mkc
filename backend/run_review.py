"""
run_review.py

Orchestrator — the "does the pipeline work at all" script.

Flow:
  git diff -> hunks -> (per hunk) prompt -> LLM -> parse findings
  -> fan out to ws_broadcaster (stub) + report_generator (stub)

This is the ugly end-to-end path from Section 12 of the knowledge file.
No chunking, single model (Phi-3 Mini via Ollama), stubs for mobile/report.

USAGE:
  python run_review.py                 # reviews the last commit in the current repo
  python run_review.py --staged        # reviews staged (git add'ed) changes instead
  python run_review.py --repo /path    # point at a different repo
"""

import argparse
import time
from collections import defaultdict

from diff_extractor import get_last_commit_diff, get_diff, split_into_hunks
from prompt_builder import build_prompt
from llm_client import review_hunk
from response_parser import parse_findings
from ws_broadcaster import broadcast_findings
from report_generator import generate_report


def main():
    parser = argparse.ArgumentParser(description="DevMesh skeleton pipeline runner")
    parser.add_argument("--repo", default=".", help="Path to the git repo to review")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Review staged changes instead of the last commit",
    )
    args = parser.parse_args()

    print(f"[run_review] Extracting diff from: {args.repo}")
    if args.staged:
        raw_diff = get_diff(args.repo, staged=True)
    else:
        raw_diff = get_last_commit_diff(args.repo)

    hunks = split_into_hunks(raw_diff)
    print(f"[run_review] Found {len(hunks)} hunk(s) to review\n")

    if not hunks:
        print("No hunks found — nothing to review (empty diff, or no commits yet).")
        return

    all_findings = defaultdict(list)
    total_latency = 0.0

    for i, hunk in enumerate(hunks, start=1):
        print(f"[run_review] Reviewing hunk {i}/{len(hunks)}: {hunk.file_path} (line {hunk.start_line})")
        prompt = build_prompt(hunk)

        start = time.time()
        result = review_hunk(prompt)
        elapsed = time.time() - start
        total_latency += elapsed

        findings = parse_findings(result.raw_output)
        all_findings[hunk.file_path].extend(findings)

        print(f"    -> {len(findings)} finding(s), {elapsed:.2f}s")

    print(f"\n[run_review] Total LLM latency: {total_latency:.2f}s across {len(hunks)} call(s)")
    print(f"[run_review] Average per hunk: {total_latency / len(hunks):.2f}s\n")

    # Fan out #1: mobile (stub)
    for file_path, findings in all_findings.items():
        if findings:
            broadcast_findings(findings, file_path)

    # Fan out #2: report (stub)
    report_path = generate_report(dict(all_findings))
    print(f"\n[run_review] Report written to: {report_path}")


if __name__ == "__main__":
    main()
