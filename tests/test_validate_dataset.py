"""Focused tests for the read-only dataset validation utility."""

from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.validate_dataset import REQUIRED_COLUMNS, validate_dataset


HEADER = ",".join(REQUIRED_COLUMNS)


def write_csv(directory: str, rows: list[list[str]], header: str = HEADER) -> Path:
    path = Path(directory) / "synthetic.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header.split(","))
        writer.writerows(rows)
    return path


def row(
    project_id: str = "SYNTH-001",
    title: str = "MOCK ONLY title",
    abstract: str = "MOCK ONLY: a distinct synthetic description of a sensor system.",
    tech_stack: str = "Python, sensor",
    domain: str = "test-only",
    source_type: str = "MOCK ONLY",
    source_url: str = "",
    year: str = "2025",
) -> list[str]:
    return [project_id, title, abstract, tech_stack, domain, source_type, source_url, year]


def test_valid_csv_has_no_blocking_errors_and_input_is_unchanged() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(directory, [row()])
        original = path.read_bytes()
        report = validate_dataset(path)
        assert report.valid
        assert report.errors == []
        assert report.records_inspected == 1
        assert path.read_bytes() == original


def test_missing_required_columns_is_blocking() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(directory, [row()], header="project_id,title,abstract")
        report = validate_dataset(path)
    assert not report.valid
    assert "Missing required column(s): tech_stack" in report.errors[0]


def test_duplicate_project_ids_are_blocking() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(directory, [row(), row(project_id=" SYNTH-001 ", title="Second synthetic title")])
        report = validate_dataset(path)
    assert any("duplicate project_id 'SYNTH-001'" in error for error in report.errors)


def test_malformed_nonempty_year_is_blocking() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(directory, [row(year="2024.5")])
        report = validate_dataset(path)
    assert any("malformed year '2024.5'" in error for error in report.errors)


def test_invalid_nonempty_url_is_blocking() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(directory, [row(source_url="javascript:alert(1)")])
        report = validate_dataset(path)
    assert any("invalid source_url" in error for error in report.errors)


def test_repeated_source_url_is_warning_not_blocking_error() -> None:
    with TemporaryDirectory() as directory:
        shared = "https://example.test/source"
        path = write_csv(
            directory,
            [row(source_url=shared), row(project_id="SYNTH-002", source_url=shared + "/")],
        )
        report = validate_dataset(path)
    assert report.valid
    assert any("Source URL is shared" in warning for warning in report.warnings)


def test_repeated_opening_and_templated_abstracts_are_warnings() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(
            directory,
            [
                row(abstract="This project proposes a system that monitors crop health with sensors."),
                row(
                    project_id="SYNTH-002",
                    abstract="This project proposes a system that monitors water quality with sensors.",
                ),
            ],
        )
        report = validate_dataset(path)
    assert report.valid
    assert any("Abstract opening is repeated" in warning for warning in report.warnings)


def test_empty_description_and_stack_are_warnings() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(directory, [row(abstract="", tech_stack="")])
        report = validate_dataset(path)
    assert report.valid
    assert any("abstract/description is empty" in warning for warning in report.warnings)
    assert any("tech_stack is empty" in warning for warning in report.warnings)

def test_placeholder_values_and_identical_stacks_are_warnings() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(
            directory,
            [
                row(title="placeholder", tech_stack="Python, C++"),
                row(project_id="SYNTH-002", title="Another synthetic title", tech_stack="Python, C++"),
            ],
        )
        report = validate_dataset(path)
    assert report.valid
    assert any("placeholder-like text" in warning for warning in report.warnings)
    assert any("Technology stack is identical" in warning for warning in report.warnings)


def test_mixed_source_provenance_is_a_review_warning() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(
            directory,
            [
                row(source_type="institutional archive"),
                row(project_id="SYNTH-002", source_type="open dataset"),
            ],
        )
        report = validate_dataset(path)
    assert report.valid
    assert any("both institutional and external indicators" in warning for warning in report.warnings)

def test_missing_project_id_and_title_are_blocking() -> None:
    with TemporaryDirectory() as directory:
        path = write_csv(directory, [row(project_id="", title="" )])
        report = validate_dataset(path)
    assert any("project_id is missing" in error for error in report.errors)
    assert any("title is missing" in error for error in report.errors)