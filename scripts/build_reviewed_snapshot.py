"""Build a version-1 reviewed evaluator snapshot from human-completed annotations."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluation_workflow import build_reviewed_snapshot, read_json, write_json_new


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Original immutable version-1 capture JSON")
    parser.add_argument("annotations", type=Path, help="Human-completed annotation CSV exported from this capture")
    parser.add_argument("--output", required=True, type=Path, help="New reviewed snapshot JSON path; existing files are never overwritten")
    args = parser.parse_args()
    try:
        capture, _ = read_json(args.capture)
        result = build_reviewed_snapshot(capture, args.annotations)
        write_json_new(args.output, result)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    candidates = sum(len(case["candidates"]) for case in result["cases"])
    print(f"Built reviewed snapshot with {len(result['cases'])} queries and {candidates} human-labelled candidates at {args.output}.")
    print("No labels were generated; all grades and rationales came from the annotation CSV.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
