"""Read-only structural and review validation for Idea Enhancer CSV datasets."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED_COLUMNS = (
    "project_id",
    "title",
    "abstract",
    "tech_stack",
    "domain",
    "source_type",
    "source_url",
    "year",
)

_PLACEHOLDER = re.compile(
    r"\b(?:placeholder|tbd|to be determined|unknown|not available|n/?a|mock only|dummy value|lorem ipsum)\b",
    re.IGNORECASE,
)
_INSTITUTIONAL_MARKERS = ("institution", "rvce", "college", "university", "campus", "internal", "archive")
_EXTERNAL_MARKERS = ("external", "open", "global", "github", "kaggle", "arxiv", "dataset", "web")


@dataclass
class ValidationReport:
    """Blocking errors and review-only warnings collected from one CSV."""

    path: Path
    records_inspected: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """Whether the CSV has no blocking structural errors."""

        return not self.errors


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _valid_url(value: str) -> bool:
    if any(character.isspace() for character in value):
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return False
        _ = parsed.port  # Access validates malformed/out-of-range ports.
    except ValueError:
        return False
    return True


def _normalized_url(value: str) -> str:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").casefold()
    port = f":{parsed.port}" if parsed.port is not None else ""
    path = parsed.path.rstrip("/")
    normalized = f"{parsed.scheme.casefold()}://{host}{port}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    if parsed.fragment:
        normalized += f"#{parsed.fragment}"
    return normalized


def _add_repeated_value_warnings(
    report: ValidationReport,
    values: dict[str, list[int]],

    *,
    message: str,
) -> None:
    for value, rows in sorted(values.items()):
        if len(rows) > 1:
            report.warnings.append(
                f"{message}: {value!r} appears in {len(rows)} records (CSV rows {', '.join(map(str, rows))}); review manually."
            )


def validate_dataset(path: str | Path) -> ValidationReport:
    """Inspect a CSV without changing it; warnings never invalidate a dataset."""

    dataset_path = Path(path)
    report = ValidationReport(path=dataset_path)
    try:
        source = dataset_path.open("r", encoding="utf-8-sig", newline="")
    except (OSError, UnicodeError) as error:
        report.errors.append(f"Cannot read {dataset_path}: {error}")
        return report

    repeated_urls: dict[str, list[int]] = defaultdict(list)
    repeated_abstracts: dict[str, list[int]] = defaultdict(list)
    repeated_abstract_openings: dict[str, list[int]] = defaultdict(list)
    repeated_stacks: dict[str, list[int]] = defaultdict(list)
    provenance_kinds: set[str] = set()
    seen_ids: dict[str, int] = {}

    try:
        with source:
            reader = csv.reader(source, strict=True)
            try:
                headers = [column.strip() for column in next(reader)]
            except StopIteration:
                report.errors.append("CSV is empty and has no header row.")
                return report

            if len(headers) != len(set(headers)):
                report.errors.append("CSV header contains duplicate column names.")
                return report
            missing = [column for column in REQUIRED_COLUMNS if column not in headers]
            if missing:
                report.errors.append(f"Missing required column(s): {', '.join(missing)}.")
                return report

            for row in reader:
                row_number = reader.line_num
                report.records_inspected += 1
                if len(row) != len(headers):
                    report.errors.append(
                        f"CSV row {row_number}: expected {len(headers)} fields from the header, got {len(row)}."
                    )
                    continue
                record = {key: value.strip() for key, value in zip(headers, row)}

                project_id = record["project_id"]
                if not project_id:
                    report.errors.append(f"CSV row {row_number}: project_id is missing.")
                elif project_id in seen_ids:
                    report.errors.append(
                        f"CSV row {row_number}: duplicate project_id {project_id!r} (first seen on row {seen_ids[project_id]})."
                    )
                else:
                    seen_ids[project_id] = row_number

                if not record["title"]:
                    report.errors.append(f"CSV row {row_number}: title is missing.")

                year = record["year"]
                if year and not re.fullmatch(r"[+-]?\d+", year):
                    report.errors.append(f"CSV row {row_number}: malformed year {year!r}; expected a whole number or blank.")

                url = record["source_url"]
                if url and not _valid_url(url):
                    report.errors.append(f"CSV row {row_number}: invalid source_url {url!r}; expected an http(s) URL with a host.")
                elif url:
                    repeated_urls[_normalized_url(url)].append(row_number)

                abstract = record["abstract"]
                stack = record["tech_stack"]
                if not abstract:
                    report.warnings.append(f"CSV row {row_number}: abstract/description is empty; review source data.")
                else:
                    normalized_abstract = _normalized(abstract)
                    repeated_abstracts[normalized_abstract].append(row_number)
                    words = normalized_abstract.split()
                    if len(words) >= 6:
                        repeated_abstract_openings[" ".join(words[:6])].append(row_number)
                if not stack:
                    report.warnings.append(f"CSV row {row_number}: tech_stack is empty; review source data.")
                else:
                    repeated_stacks[_normalized(stack)].append(row_number)

                for column in ("title", "abstract", "tech_stack", "domain", "source_type", "source_url"):
                    value = record[column]
                    if value and _PLACEHOLDER.search(value):
                        report.warnings.append(
                            f"CSV row {row_number}: {column} contains placeholder-like text {value!r}; review manually."
                        )

                source_type = _normalized(record["source_type"])
                if any(marker in source_type for marker in _INSTITUTIONAL_MARKERS):
                    provenance_kinds.add("institutional")
                if any(marker in source_type for marker in _EXTERNAL_MARKERS):
                    provenance_kinds.add("external")

    except (OSError, UnicodeError, csv.Error) as error:
        report.errors.append(f"Could not parse CSV {dataset_path}: {error}")
        return report

    if report.records_inspected == 0:
        report.errors.append("CSV has a header but contains no records.")

    _add_repeated_value_warnings(
        report, repeated_urls, message="Source URL is shared"
    )
    _add_repeated_value_warnings(
        report, repeated_abstracts, message="Abstract is repeated"
    )
    _add_repeated_value_warnings(
        report,
        repeated_abstract_openings,

        message="Abstract opening is repeated; descriptions may be templated",
    )
    _add_repeated_value_warnings(
        report,
        repeated_stacks,

        message="Technology stack is identical",
    )
    if provenance_kinds == {"institutional", "external"}:
        report.warnings.append(
            "Source types include both institutional and external indicators; review provenance labeling across records."
        )
    return report


def format_report(report: ValidationReport) -> str:
    """Format a human-readable report with errors separated from warnings."""

    lines = [f"Dataset: {report.path}", f"Records inspected: {report.records_inspected}"]
    lines.extend(f"ERROR: {message}" for message in report.errors)
    lines.extend(f"WARNING: {message}" for message in report.warnings)
    if report.errors:
        lines.append(f"Result: FAILED ({len(report.errors)} blocking error(s), {len(report.warnings)} review warning(s))")
    elif report.warnings:
        lines.append(f"Result: REVIEW ({len(report.warnings)} review warning(s), no blocking errors)")
    else:
        lines.append("Result: PASS (no blocking errors or review warnings)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only validator for Idea Enhancer CSV datasets.")
    parser.add_argument("csv_path", type=Path, help="path to the CSV file to inspect")
    args = parser.parse_args(argv)
    report = validate_dataset(args.csv_path)
    print(format_report(report))
    return 0 if report.valid else 1


if __name__ == "__main__":
    sys.exit(main())