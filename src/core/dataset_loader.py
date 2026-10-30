"""Strict loader for the approved canonical project CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from src.core.contracts import ProjectRecord


CANONICAL_DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "historical_projects.csv"
REQUIRED_COLUMNS = ("project_id", "title", "abstract", "source_type")
OPTIONAL_COLUMNS = ("tech_stack", "domain", "source_url", "year")
CANONICAL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class DatasetLoadError(ValueError):
    """The canonical dataset could not be safely loaded."""


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _optional_preserving_text(value: str | None) -> str | None:
    """Map blank metadata to None while keeping supplied nonblank text intact."""

    if value is None or not value.strip():
        return None
    return value


def _record_from_row(row: dict[str, str | None], row_number: int) -> ProjectRecord:
    project_id = (row.get("project_id") or "").strip()
    if not project_id:
        raise DatasetLoadError(f"CSV row {row_number}: project_id must not be empty.")

    title = (row.get("title") or "").strip()
    if not title:
        raise DatasetLoadError(f"CSV row {row_number}: title must not be empty.")

    abstract = (row.get("abstract") or "").strip()
    if not abstract:
        raise DatasetLoadError(f"CSV row {row_number}: abstract must not be empty.")

    source_type = row.get("source_type") or ""
    if not source_type.strip():
        raise DatasetLoadError(f"CSV row {row_number}: source_type must not be empty.")

    year_text = _optional_text(row.get("year"))
    year: int | None = None
    if year_text is not None:
        try:
            year = int(year_text)
        except ValueError as error:
            raise DatasetLoadError(
                f"CSV row {row_number}: year must be a whole number when present; got {year_text!r}."
            ) from error

    return ProjectRecord(
        project_id=project_id,
        title=title,
        abstract=abstract,
        tech_stack=_optional_text(row.get("tech_stack")),
        domain=_optional_text(row.get("domain")),
        source_type=source_type,
        source_url=_optional_preserving_text(row.get("source_url")),
        year=year,
    )


def load_project_records(path: str | Path = CANONICAL_DATASET_PATH) -> list[ProjectRecord]:
    """Load and validate every row; fail with row context rather than skipping data."""

    dataset_path = Path(path)
    if not dataset_path.is_file():
        raise DatasetLoadError(
            f"Canonical dataset not found at {dataset_path.name}. Prepare data/historical_projects.csv first."
        )

    records: list[ProjectRecord] = []
    seen_ids: set[str] = set()

    try:
        with dataset_path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source, strict=True)
            try:
                raw_headers = next(reader)
            except StopIteration as error:
                raise DatasetLoadError(f"Dataset {dataset_path.name} is empty and has no CSV header.") from error

            headers = [header.strip() for header in raw_headers]
            if len(headers) != len(set(headers)):
                raise DatasetLoadError(f"Dataset {dataset_path.name} has duplicate column names in its header.")
            missing = [column for column in REQUIRED_COLUMNS if column not in headers]
            if missing:
                raise DatasetLoadError(
                    f"Dataset {dataset_path.name} is missing required column(s): {', '.join(missing)}."
                )

            row_count = 0
            for values in reader:
                row_count += 1
                row_number = reader.line_num
                if len(values) != len(headers):
                    raise DatasetLoadError(
                        f"CSV row {row_number}: expected {len(headers)} fields from the header, got {len(values)}."
                    )
                row = dict(zip(headers, values))
                record = _record_from_row(row, row_number)
                if record.project_id in seen_ids:
                    raise DatasetLoadError(
                        f"CSV row {row_number}: duplicate project_id {record.project_id!r}."
                    )
                seen_ids.add(record.project_id)
                records.append(record)

            if row_count == 0:
                raise DatasetLoadError(f"Dataset {dataset_path.name} contains a header but no project records.")
    except DatasetLoadError:
        raise
    except (OSError, UnicodeError, csv.Error) as error:
        raise DatasetLoadError(f"Could not read dataset {dataset_path.name}: {error}") from error

    return records
