from __future__ import annotations

import argparse
import collections
import logging
import sys
import time

from cell_classification import CATEGORY_ORDER, classify_record, write_classified_records
from csv_ingestion import CsvIngestionError, iter_records
from nutrition_jpg_renderer import render_nutrition_jpgs_pipeline
from nutrition_parser import parse_nutrition_fields
from reporting_exports import write_reporting_artifacts
from runtime_config import RuntimeConfigError, parse_bool, resolve_runtime_config
from runtime_logging import initialize_run_logging
from text_normalization import normalize_nutrition_text
from validation_status import assign_validation_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Naehrwert JPG Generator - local one-off CLI scaffold"
    )
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument("--output", required=True, help="Path to output directory")
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Worker count for parallel operations (default: 6)",
    )
    parser.add_argument(
        "--resume",
        type=parse_bool,
        default=True,
        help="Resume mode true/false (default: true). false enables overwrite behavior.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional limit for test-mode runs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = resolve_runtime_config(
            input_arg=args.input,
            output_arg=args.output,
            workers=args.workers,
            resume=args.resume,
            limit=args.limit,
        )
    except RuntimeConfigError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 2

    log_path = initialize_run_logging(config.output_dir)
    logger = logging.getLogger(__name__)
    run_started_at = time.perf_counter()

    try:
        logger.info("CLI startup complete")
        logger.info(config.startup_summary())
        logger.info("Run log file: %s", log_path)
        logger.info("Pipeline stage started | stage=ingestion")

        record_stream, stats = iter_records(
            input_path=config.input_path,
            logger=logger,
            limit=config.limit,
        )
        logger.info("Pipeline stage started | stage=classification_normalization_parsing_validation")

        classified_records = []
        normalization_warning_total = 0
        parser_warning_total = 0
        validation_warning_total = 0
        status_counter: collections.Counter[str] = collections.Counter()

        for record in record_stream:
            normalization_result = normalize_nutrition_text(record.nutrition_raw_text)
            if normalization_result.warnings:
                normalization_warning_total += len(normalization_result.warnings)
                logger.warning(
                    "Normalization warnings for row=%s product_id=%s warnings=%s",
                    record.row_number,
                    record.product_id,
                    list(normalization_result.warnings),
                )

            classified_record = classify_record(
                record,
                nutrition_normalized_text=normalization_result.normalized_text,
                nutrition_search_text=normalization_result.search_text,
                normalization_warnings=normalization_result.warnings,
            )

            parse_result = parse_nutrition_fields(
                normalized_text=classified_record.nutrition_normalized_text,
                category=classified_record.category,
            )
            if parse_result.warnings:
                parser_warning_total += len(parse_result.warnings)
                logger.warning(
                    "Parser warnings for row=%s product_id=%s warnings=%s",
                    record.row_number,
                    record.product_id,
                    list(parse_result.warnings),
                )

            enriched_record = classify_record(
                record,
                nutrition_normalized_text=classified_record.nutrition_normalized_text,
                nutrition_search_text=classified_record.nutrition_search_text,
                normalization_warnings=classified_record.normalization_warnings,
                extracted_nutrition=parse_result.fields,
                parser_warnings=parse_result.warnings,
                parser_basis=parse_result.parse_basis,
            )

            validation_status = assign_validation_status(enriched_record)
            if validation_status.validation_warnings:
                validation_warning_total += len(validation_status.validation_warnings)
                logger.warning(
                    "Validation warnings for row=%s product_id=%s warnings=%s",
                    record.row_number,
                    record.product_id,
                    list(validation_status.validation_warnings),
                )

            status_counter[validation_status.status] += 1
            classified_records.append(
                classify_record(
                    record,
                    nutrition_normalized_text=enriched_record.nutrition_normalized_text,
                    nutrition_search_text=enriched_record.nutrition_search_text,
                    normalization_warnings=enriched_record.normalization_warnings,
                    extracted_nutrition=parse_result.fields,
                    parser_warnings=parse_result.warnings,
                    parser_basis=parse_result.parse_basis,
                    parsed_fields_count=validation_status.parsed_fields_count,
                    validation_warnings=validation_status.validation_warnings,
                    status=validation_status.status,
                    status_reasons=validation_status.status_reasons,
                    hard_failure_reasons=validation_status.hard_failure_reasons,
                )
            )

        logger.info("Pipeline stage completed | stage=classification_normalization_parsing_validation records=%s", len(classified_records))

        classified_output_path = config.output_dir / "classified_records.jsonl"
        logger.info("Pipeline stage started | stage=persistence_classified_records")
        write_classified_records(classified_output_path, classified_records)
        logger.info(
            "Pipeline stage completed | stage=persistence_classified_records output=%s records=%s",
            classified_output_path,
            len(classified_records),
        )

        logger.info("Pipeline stage started | stage=reporting")
        report_artifacts = write_reporting_artifacts(
            config.output_dir,
            classified_records,
            ingestion_rejected_records=stats.rejected_records,
        )
        logger.info("Pipeline stage completed | stage=reporting")

        render_output_dir = config.output_dir / "output"
        logger.info("Pipeline stage started | stage=rendering")
        render_result = render_nutrition_jpgs_pipeline(
            records=classified_records,
            output_dir=render_output_dir,
            workers=config.workers,
            resume=config.resume,
        )
        logger.info("Pipeline stage completed | stage=rendering")

        category_counter = collections.Counter(record.category for record in classified_records)
        category_summary = {category: category_counter.get(category, 0) for category in CATEGORY_ORDER}

        logger.info(
            "Classification completed | output=%s classified=%s categories=%s",
            classified_output_path,
            len(classified_records),
            category_summary,
        )
        logger.info(
            "Text normalization completed | records=%s warning_count=%s",
            len(classified_records),
            normalization_warning_total,
        )
        logger.info(
            "Nutrition extraction completed | records=%s warning_count=%s",
            len(classified_records),
            parser_warning_total,
        )
        logger.info(
            "Validation/status assignment completed | records=%s warning_count=%s statuses=%s",
            len(classified_records),
            validation_warning_total,
            dict(status_counter),
        )
        logger.info(
            "Reporting completed | report=%s needs_review=%s failed=%s",
            report_artifacts.report_path,
            report_artifacts.needs_review_path,
            report_artifacts.failed_path,
        )
        logger.info(
            "Reporting summary | categories=%s statuses=%s",
            report_artifacts.category_summary,
            report_artifacts.status_summary,
        )
        logger.info(
            "Rendering completed | output_root=%s eligible_total=%s rendered=%s skipped_existing=%s failed_render=%s",
            render_output_dir,
            render_result.total_eligible_count,
            len(render_result.rendered_paths),
            len(render_result.skipped_existing_ids),
            len(render_result.failures),
        )

        for failure in render_result.failures:
            logger.error(
                "Render failed for product_id=%s error=%s",
                failure.product_id,
                failure.error,
            )

        logger.info(
            "CSV ingestion completed | encoding=%s total=%s valid=%s skipped=%s",
            stats.used_encoding,
            stats.total_rows,
            stats.valid_rows,
            stats.skipped_rows,
        )
        logger.info(
            "CSV ingestion reject visibility | surfaced_failed_rows=%s",
            len(stats.rejected_records),
        )
        logger.info(
            "Pipeline run completed | duration_ms=%s records_processed=%s ingest_valid=%s ingest_skipped=%s rendered=%s render_skipped_existing=%s render_skipped_non_renderable=%s render_failed=%s",
            int((time.perf_counter() - run_started_at) * 1000),
            len(classified_records),
            stats.valid_rows,
            stats.skipped_rows,
            len(render_result.rendered_paths),
            len(render_result.skipped_existing_ids),
            len(render_result.skipped_non_renderable_ids),
            len(render_result.failures),
        )
        return 0
    except CsvIngestionError as exc:
        logger.error("Fatal ingestion configuration error: %s", exc)
        return 2
    except Exception:
        logger.exception("Fatal runtime error during startup")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
