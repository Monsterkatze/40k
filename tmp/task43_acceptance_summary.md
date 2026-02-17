# Task 4.3 Acceptance Summary

## Sampling Method (Deterministic)
- Source pool: `tmp/out_task42_full/classified_records.jsonl` with statuses in {OK, OK_WITH_WARNINGS}.
- Random seed: `43`; deterministic order by `(product_id, row_number)` before seeded shuffle.
- Target sample size: `200`; available eligible records: `2`; actual sampled: `2`.

## KPI Table
| KPI | Value | Interpretation |
|---|---:|---|
| Eligible auto-processed pool (full run) | 2 | Below required 200; proportional reporting applied |
| Manual correctness hits | 2/2 | Proportional acceptance hit rate basis |
| Proportional quality rate | 100.0% | Against available sample only |
| Target threshold | 160/200 (>=80.0%) | Formal target requires 200-sample pool |
| Target attainment status | proportional_only | Not claimable as full-target pass due to sample-size limitation |
| Full-run status distribution | {'OK': 2, 'NEEDS_REVIEW': 1} | Parser/model quality outcomes on classified records |
| UTF-edge FAILED rows (ingestion rejects) | 3 | Input-quality observability, not parser extraction failures |

## Acceptance Decision Context
- Parser/model quality on available full-run eligible records is strong (sampled records manually marked correct).
- Formal 200-sample acceptance target cannot be conclusively validated because eligible pool is only 2 in current full run.
- Updated FAILED semantics are confirmed: ingestion rejects are now surfaced for observability and must be interpreted separately from classified parsing quality.

## Residual Risks / Open Cases
- Sample-size limitation risks overestimating generalization; rerun on a materially larger dataset is needed for definitive acceptance.
- Mixed-content and non-NUTRITION category coverage remains low in current evidence window.

## One-off Handover Note
- Task 4.2 improvements remain stable and beneficial; proceed to project closure only with explicit acknowledgment of proportional acceptance limitation.
- Ingestion-visibility evidence line: `2026-02-13 09:27:52 | INFO | CSV ingestion reject visibility | surfaced_failed_rows=3`

## Artifacts
- `tmp/task43_acceptance_sample_review.csv`
- `tmp/task43_acceptance_summary.md`
- `tmp/out_task42_full/{classified_records.jsonl,report.csv,needs_review.csv,failed.csv,run.log}`
- `tmp/out_task42_utf/{report.csv,needs_review.csv,failed.csv,run.log}`