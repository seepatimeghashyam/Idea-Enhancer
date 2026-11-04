"""Export a capture as an unbiased human relevance annotation CSV."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluation_workflow import complete_capture, read_json, write_csv_new


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Version-1 full-pool live capture JSON")
    parser.add_argument("--output", required=True, type=Path, help="New annotation CSV path; existing files are never overwritten")
    args = parser.parse_args()
    try:
        value, _ = read_json(args.capture)
        capture = complete_capture(value)
        row_count = write_csv_new(args.output, capture)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(f"Exported {row_count} pending candidate annotations to {args.output}; no grades were assigned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
