"""Standard-library tests for the documented canonical CSV loader contract."""

from __future__ import annotations

import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from src.core.dataset_loader import DatasetLoadError, load_project_records


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FULL_HEADER = "project_id,title,abstract,tech_stack,domain,source_type,source_url,year\n"
REQUIRED_HEADER = "project_id,title,abstract,source_type\n"


@contextmanager
def temporary_csv(contents: str) -> Iterator[Path]:
    """Create disposable CSV test input under the writable project directory."""

    with TemporaryDirectory(dir=PROJECT_ROOT) as directory:
        csv_path = Path(directory) / "synthetic.csv"
        csv_path.write_text(contents, encoding="utf-8", newline="")
        yield csv_path


class DatasetLoaderTests(unittest.TestCase):
    def test_loads_valid_csv_and_maps_canonical_fields(self) -> None:
        with temporary_csv(
            FULL_HEADER
            + "SYNTHETIC-001,MOCK ONLY title,MOCK ONLY abstract,MOCK stack,MOCK domain,MOCK origin,MOCK reference,2024\n"
        ) as csv_path:
            record = load_project_records(csv_path)[0]

        self.assertEqual(record.project_id, "SYNTHETIC-001")
        self.assertEqual(record.title, "MOCK ONLY title")
        self.assertEqual(record.abstract, "MOCK ONLY abstract")
        self.assertEqual(record.tech_stack, "MOCK stack")
        self.assertEqual(record.domain, "MOCK domain")
        self.assertEqual(record.source_type, "MOCK origin")
        self.assertEqual(record.source_url, "MOCK reference")
        self.assertEqual(record.year, 2024)

    def test_missing_required_header_is_rejected(self) -> None:
        with temporary_csv("project_id,title,abstract\nSYNTHETIC-001,MOCK,MOCK\n") as csv_path:
            with self.assertRaisesRegex(DatasetLoadError, "missing required column.*source_type"):
                load_project_records(csv_path)

    def test_empty_and_whitespace_project_ids_are_rejected(self) -> None:
        for project_id in ("", "   "):
            with self.subTest(project_id=project_id):
                row = f'"{project_id}",MOCK ONLY title,MOCK ONLY abstract,MOCK ONLY\n'
                with temporary_csv(REQUIRED_HEADER + row) as csv_path:
                    with self.assertRaisesRegex(DatasetLoadError, "project_id must not be empty"):
                        load_project_records(csv_path)

    def test_duplicate_project_ids_are_rejected(self) -> None:
        rows = (
            "SYNTHETIC-DUP,MOCK ONLY title,MOCK ONLY abstract,MOCK ONLY\n"
            "SYNTHETIC-DUP,MOCK ONLY other title,MOCK ONLY other abstract,MOCK ONLY\n"
        )
        with temporary_csv(REQUIRED_HEADER + rows) as csv_path:
            with self.assertRaisesRegex(DatasetLoadError, "CSV row 3: duplicate project_id"):
                load_project_records(csv_path)

    def test_missing_required_content_fields_are_rejected(self) -> None:
        invalid_rows = (
            "SYNTHETIC-001,,MOCK ONLY abstract,MOCK ONLY\n",
            "SYNTHETIC-001,MOCK ONLY title,   ,MOCK ONLY\n",
            "SYNTHETIC-001,MOCK ONLY title,MOCK ONLY abstract,   \n",
        )
        for row in invalid_rows:
            with self.subTest(row=row):
                with temporary_csv(REQUIRED_HEADER + row) as csv_path:
                    with self.assertRaises(DatasetLoadError):
                        load_project_records(csv_path)

    def test_blank_or_absent_optional_metadata_maps_to_none(self) -> None:
        with temporary_csv(
            FULL_HEADER + "SYNTHETIC-001,MOCK ONLY title,MOCK ONLY abstract,,,MOCK ONLY,,\n"
        ) as csv_path:
            record = load_project_records(csv_path)[0]
        self.assertIsNone(record.tech_stack)
        self.assertIsNone(record.domain)
        self.assertIsNone(record.source_url)
        self.assertIsNone(record.year)

        with temporary_csv(
            REQUIRED_HEADER + "SYNTHETIC-002,MOCK ONLY title,MOCK ONLY abstract,MOCK ONLY\n"
        ) as csv_path:
            record_without_optional_columns = load_project_records(csv_path)[0]
        self.assertIsNone(record_without_optional_columns.tech_stack)
        self.assertIsNone(record_without_optional_columns.domain)
        self.assertIsNone(record_without_optional_columns.source_url)
        self.assertIsNone(record_without_optional_columns.year)

    def test_valid_and_invalid_year_values(self) -> None:
        with temporary_csv(
            FULL_HEADER + "SYNTHETIC-001,MOCK ONLY title,MOCK ONLY abstract,,,MOCK ONLY,,2025\n"
        ) as csv_path:
            self.assertEqual(load_project_records(csv_path)[0].year, 2025)

        with temporary_csv(
            FULL_HEADER + "SYNTHETIC-001,MOCK ONLY title,MOCK ONLY abstract,,,MOCK ONLY,,unknown\n"
        ) as csv_path:
            with self.assertRaisesRegex(DatasetLoadError, "CSV row 2: year must be a whole number"):
                load_project_records(csv_path)

    def test_missing_file_is_reported(self) -> None:
        with TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            missing = Path(directory) / "not-created.csv"
            with self.assertRaisesRegex(DatasetLoadError, "Canonical dataset not found"):
                load_project_records(missing)

    def test_empty_file_and_header_only_dataset_are_rejected(self) -> None:
        for contents, expected in (("", "empty and has no CSV header"), (REQUIRED_HEADER, "no project records")):
            with self.subTest(contents=contents):
                with temporary_csv(contents) as csv_path:
                    with self.assertRaisesRegex(DatasetLoadError, expected):
                        load_project_records(csv_path)

    def test_malformed_csv_and_row_width_are_rejected(self) -> None:
        malformed_cases = (
            (REQUIRED_HEADER + 'SYNTHETIC-001,"unterminated,MOCK ONLY abstract,MOCK ONLY\n', "Could not read dataset"),
            (REQUIRED_HEADER + "SYNTHETIC-001,MOCK ONLY\n", "CSV row 2: expected 4 fields"),
        )
        for contents, expected in malformed_cases:
            with self.subTest(expected=expected):
                with temporary_csv(contents) as csv_path:
                    with self.assertRaisesRegex(DatasetLoadError, expected):
                        load_project_records(csv_path)


if __name__ == "__main__":
    unittest.main()
