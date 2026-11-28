#!/usr/bin/env python3
"""Audit dataset quality and identify records needing review."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import Counter


DATASET_PATH = Path("data/historical_projects.csv")
OUTPUT_DIR = Path("data/quality_audit")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    with DATASET_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    placeholder_rows = []
    empty_tech_rows = []
    missing_url_rows = []

    for i, row in enumerate(rows, start=2):  # 1-indexed + header
        if row["abstract"].strip() == "Description not independently verified.":
            placeholder_rows.append({"row": i, "project_id": row["project_id"], "title": row["title"], "source_url": row["source_url"]})
        if not row["tech_stack"].strip():
            empty_tech_rows.append({"row": i, "project_id": row["project_id"], "title": row["title"]})
        if not row["source_url"].strip():
            missing_url_rows.append({"row": i, "project_id": row["project_id"], "title": row["title"]})

    # Summary
    summary = {
        "total_records": len(rows),
        "placeholder_abstracts": len(placeholder_rows),
        "empty_tech_stack": len(empty_tech_rows),
        "missing_source_url": len(missing_url_rows),
        "source_type_distribution": dict(Counter(r["source_type"] for r in rows)),
        "year_distribution": dict(sorted(Counter(r["year"] for r in rows if r["year"].strip()).items())),
    }

    print(json.dumps(summary, indent=2))

    # Write detailed reports
    (OUTPUT_DIR / "placeholder_abstracts.json").write_text(json.dumps(placeholder_rows, indent=2))
    (OUTPUT_DIR / "empty_tech_stack.json").write_text(json.dumps(empty_tech_rows[:100], indent=2))  # Sample
    (OUTPUT_DIR / "missing_source_urls.json").write_text(json.dumps(missing_url_rows, indent=2))
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))

    # Create review spreadsheet for placeholder abstracts (top priority)
    review_csv = OUTPUT_DIR / "placeholder_review.csv"
    with review_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["row", "project_id", "title", "source_url", "verified_title", "verified_abstract", "tech_stack", "reuse_status", "notes"])
        for r in placeholder_rows:
            writer.writerow([r["row"], r["project_id"], r["title"], r["source_url"], "", "", "", "", ""])

    print(f"\nReports written to {OUTPUT_DIR}/")
    print(f"Review spreadsheet: {review_csv}")


if __name__ == "__main__":
    main()