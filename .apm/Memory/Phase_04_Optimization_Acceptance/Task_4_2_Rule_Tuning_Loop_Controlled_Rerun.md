---
agent: Agent_Optimization
task_ref: Task 4.2 - Rule Tuning Loop & Controlled Re-run
status: Completed
ad_hoc_delegation: false
compatibility_issues: true
important_findings: true
---

# Task Log: Task 4.2 - Rule Tuning Loop & Controlled Re-run

## Summary
Implemented P1/P2/P3 rule tuning in priority order and validated via controlled and broader reruns with measurable positive impact on review load, parser warning noise, and ingestion-reject visibility.

## Details
- P1 (`validation_status.py`): refined sub-threshold profile handling:
	- `minimal_profile_ok` for exactly 2 parsed fields with energy + macro -> `OK_WITH_WARNINGS`.
	- `minimal_profile_energy_only` for single-energy-only profile -> remains `NEEDS_REVIEW`.
- P2 (`nutrition_parser.py`): suppressed false `unreadable_field:kcal` warnings by deferring unreadable warning emission until after energy-unit fallback extraction.
- P3 (`csv_ingestion.py`, `reporting_exports.py`, `main.py`): captured structured ingestion rejects and surfaced them in `failed.csv` and `FAILED` status summary accounting while preserving non-crashing skip behavior.
- Executed controlled and broader reruns and produced dedicated comparison evidence artifact.

## Output
- Modified source files:
	- `validation_status.py`
	- `nutrition_parser.py`
	- `csv_ingestion.py`
	- `reporting_exports.py`
	- `main.py`
- Comparison artifact:
	- `tmp/task42_comparison_evidence.md`
- Controlled rerun artifacts:
	- `tmp/out_task42_control/{classified_records.jsonl,report.csv,needs_review.csv,failed.csv,run.log}`
- Broader/full rerun artifacts:
	- `tmp/out_task42_full/{classified_records.jsonl,report.csv,needs_review.csv,failed.csv,run.log}`
- Ingestion-edge rerun artifacts:
	- `tmp/out_task42_utf/{classified_records.jsonl,report.csv,needs_review.csv,failed.csv,run.log}`
- Quantitative deltas (from `tmp/task42_comparison_evidence.md`):
	- Full run (`task32_input`) status distribution: baseline `{'OK_WITH_WARNINGS': 2, 'NEEDS_REVIEW': 1}` -> new `{'OK': 2, 'NEEDS_REVIEW': 1}`.
	- Full run parser warnings: baseline `{'unreadable_field:kcal': 2}` -> new `{}`.
	- UTF ingestion-edge classified statuses: baseline `{'NEEDS_REVIEW': 2}` -> new `{'OK_WITH_WARNINGS': 1, 'NEEDS_REVIEW': 1}`.
	- UTF ingestion-edge failed visibility: baseline `failed.csv=0` rows -> new `failed.csv=3` rows, matching skipped ingest rows.

## Issues
None

## Compatibility Concerns
- `FAILED` summary counts now include surfaced ingestion rejects; downstream consumers expecting previous semantics (FAILED only from classified records) may need to adapt.

## Important Findings
- No deterministic stability regressions observed: controlled and broader reruns completed successfully.
- P1 reduced `NEEDS_REVIEW` for sparse-but-valid two-field profiles while keeping single-energy profiles in `NEEDS_REVIEW`.
- P2 removed observed `kcal` warning noise without changing extracted numeric values.
- P3 closes prior observability gap between ingestion skip warnings and failure exports.

## Next Steps
- For Task 4.3 acceptance, include ingestion-reject surfaced failures in KPI interpretation and communicate the updated `FAILED` semantics.
