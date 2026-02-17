from __future__ import annotations

import collections
import csv
from dataclasses import dataclass
from pathlib import Path

from cell_classification import CATEGORY_ORDER, ClassifiedRecord
from csv_ingestion import RejectedRecord
from validation_status import (
    STATUS_FAILED,
    STATUS_NEEDS_REVIEW,
    STATUS_OK,
    STATUS_OK_WITH_WARNINGS,
)


REPORT_HEADERS: tuple[str, ...] = (
    "id",
    "name",
    "category",
    "status",
    "parsed_fields_count",
    "warnings",
    "raw_snippet",
)

STATUS_ORDER: tuple[str, ...] = (
    STATUS_OK,
    STATUS_OK_WITH_WARNINGS,
    STATUS_NEEDS_REVIEW,
    STATUS_FAILED,
)

RAW_SNIPPET_MAX_LEN = 140


@dataclass(frozen=True)
class ReportingArtifacts:
    report_path: Path
    needs_review_path: Path
    failed_path: Path
    category_summary: dict[str, int]
    status_summary: dict[str, int]


def write_reporting_artifacts(
    output_dir: Path,
    records: list[ClassifiedRecord],
    ingestion_rejected_records: list[RejectedRecord] | None = None,
) -> ReportingArtifacts:
    report_path = output_dir / "report.csv"
    needs_review_path = output_dir / "needs_review.csv"
    failed_path = output_dir / "failed.csv"

    report_rows = [_build_report_row(record) for record in records]
    rejected_rows = _build_rejected_report_rows(ingestion_rejected_records or [])
    _write_csv(report_path, report_rows)
    _write_csv(
        needs_review_path,
        [row for row in report_rows if row["status"] == STATUS_NEEDS_REVIEW],
    )
    _write_csv(
        failed_path,
        [row for row in report_rows if row["status"] == STATUS_FAILED] + rejected_rows,
    )

    category_counter = collections.Counter(record.category for record in records)
    status_counter = collections.Counter(record.status for record in records)
    status_counter[STATUS_FAILED] += len(rejected_rows)

    category_summary = {category: category_counter.get(category, 0) for category in CATEGORY_ORDER}
    status_summary = {status: status_counter.get(status, 0) for status in STATUS_ORDER}

    return ReportingArtifacts(
        report_path=report_path,
        needs_review_path=needs_review_path,
        failed_path=failed_path,
        category_summary=category_summary,
        status_summary=status_summary,
    )


def _build_report_row(record: ClassifiedRecord) -> dict[str, str]:
    warnings = _collect_warnings(record)
    return {
        "id": record.product_id,
        "name": record.product_name,
        "category": record.category,
        "status": record.status,
        "parsed_fields_count": str(record.parsed_fields_count),
        "warnings": " | ".join(warnings),
        "raw_snippet": _deterministic_snippet(record.nutrition_raw_text),
    }


def _collect_warnings(record: ClassifiedRecord) -> list[str]:
    merged = [
        *record.normalization_warnings,
        *record.parser_warnings,
        *record.validation_warnings,
        *record.status_reasons,
        *record.hard_failure_reasons,
    ]

    deduplicated: list[str] = []
    seen: set[str] = set()
    for item in merged:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        deduplicated.append(item)
    return deduplicated


def _deterministic_snippet(raw_text: str) -> str:
    normalized = " ".join(raw_text.split())
    if len(normalized) <= RAW_SNIPPET_MAX_LEN:
        return normalized
    return f"{normalized[: RAW_SNIPPET_MAX_LEN - 1]}…"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(REPORT_HEADERS))
        writer.writeheader()
        writer.writerows(rows)


def _build_rejected_report_rows(rejected_records: list[RejectedRecord]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for rejected in rejected_records:
        rows.append(
            {
                "id": rejected.product_id,
                "name": rejected.product_name,
                "category": "MISSING",
                "status": STATUS_FAILED,
                "parsed_fields_count": "0",
                "warnings": f"ingestion_reject:{rejected.reason}",
                "raw_snippet": _deterministic_snippet(rejected.nutrition_raw_text),
            }
        )
    return rows
