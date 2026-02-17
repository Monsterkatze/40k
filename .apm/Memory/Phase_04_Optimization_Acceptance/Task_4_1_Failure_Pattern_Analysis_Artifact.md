# Task 4.1 – Failure Pattern Analysis Artifact

## Scope & Sources
Analyzed recent end-to-end artifacts and prior baseline:
- `tmp/out_task33_full/{report.csv,needs_review.csv,failed.csv,classified_records.jsonl,run.log}`
- `tmp/out_task33_limit/{report.csv,needs_review.csv,failed.csv,classified_records.jsonl,run.log}`
- `tmp/out_task32/{report.csv,needs_review.csv,failed.csv,classified_records.jsonl,run.log}`
- Drift context: `tmp/out_task24_cp/*`, `tmp/out_task24_utf/*`, `tmp/task14_audit/{baseline_metrics.json,audit_report_task14.md}`

## Observed Frequency (current evidence window)
- Records analyzed (classified): **12**
- `NEEDS_REVIEW`: **6** (50%)
- `FAILED`: **0**
- Review reasons:
  - `insufficient_parsed_fields:1<3` → **3**
  - `insufficient_parsed_fields:2<3` → **3**
- Repeated text-shape cues in `NEEDS_REVIEW`:
  - `brennwert_only_no_kcal` → **3**
  - `energy_fat_only_pair` → **3**

## Prioritized Cause Classes (for Task 4.2)

### P1 — Sparse but valid nutrition profiles forced to `NEEDS_REVIEW`
- **Pattern:** short, semantically valid nutrition strings with 1–2 fields (e.g., only energy; energy+fat).
- **Evidence:**
  - `tmp/out_task33_full/needs_review.csv` (`1005`, `insufficient_parsed_fields:1<3`, snippet `Brennwert 300 kJ`)
  - `tmp/out_task24_cp/needs_review.csv` (`2001`, `2002`, `insufficient_parsed_fields:2<3`)
  - `tmp/out_task24_utf/needs_review.csv` (`1001`, `1005`)
- **Expected leverage:** **High** (dominant and recurring source of `NEEDS_REVIEW`).
- **Implementation effort:** **Low**.
- **Rule adjustment candidates:**
  1. Add a `minimal_profile_ok` gate:
     - Accept as `OK_WITH_WARNINGS` when `parsed_fields_count >= 2` and at least one energy signal (`kJ` or `kcal`) is present.
  2. Add a tighter `single_energy_review` branch:
     - Keep single-field `kJ`/`kcal` as `NEEDS_REVIEW`, but emit deterministic reason `minimal_profile_energy_only` (clearer triage than generic `<3`).
  3. Keep current hard-failure logic unchanged.

### P2 — `kcal` extraction warning noise on otherwise complete records
- **Pattern:** `unreadable_field:kcal` appears on fully parsed records where `kcal` value is present.
- **Evidence:**
  - `tmp/out_task33_full/run.log` rows 2/3 parser warnings;
  - matching records in `tmp/out_task33_full/classified_records.jsonl` have `kcal` populated and `parsed_fields_count=7`.
- **Expected leverage:** **Medium** (reduces false warning load and review trust friction, but not current `NEEDS_REVIEW` driver).
- **Implementation effort:** **Low**.
- **Rule adjustment candidates:**
  1. In parser warning generation, suppress `unreadable_field:kcal` if `extracted_nutrition.kcal` is already non-null.
  2. Normalize adjacent energy token handling (`kJ 96 kcal`) before unreadable checks.

### P3 — Ingestion-stage dropped rows not represented in `FAILED`
- **Pattern:** missing required fields are skipped during ingestion and absent from review/failure exports.
- **Evidence:**
  - `tmp/out_task24_utf/run.log` shows skipped rows for missing `id`, `name`, `nutrition_raw_text`.
  - `tmp/out_task24_utf/failed.csv` remains empty.
- **Expected leverage:** **Medium** (improves failure observability and closure loop for bad input data).
- **Implementation effort:** **Low-Medium**.
- **Rule adjustment candidates:**
  1. Emit ingestion-rejected rows into `FAILED` export via synthetic record (`status=FAILED`, reason `missing_required_field:<field>`).
  2. Keep current skip behavior for pipeline safety, but add explicit failure accounting in report summary.

## Required Coverage Notes
- **Encoding/text-normalization edge cases:** CP1252 fallback and mojibake header evidence persist in logs (`tmp/out_task24_cp/run.log`, baseline task14 audit), but current classified outputs remain deterministic.
- **Unit/number formatting irregularities:** decimal forms like `3.5 g` parse successfully; key issue is warning noise around adjacent energy tokens.
- **Mixed-content parse boundaries:** no recurring `MIXED`/boundary failures observed in current runs; continuity with Phase-1 baseline indicates fixture skew toward `NUTRITION` only.
- **Low-signal/partial-field extraction:** primary observed root cause (`parsed_fields_count < 3`) and highest leverage target.

## Recommended Task 4.2 execution order
1. Implement **P1** rule split (`minimal_profile_ok` vs `single_energy_review`) and rerun controlled subset.
2. Implement **P2** warning suppression/normalization cleanup.
3. Implement **P3** ingestion-failure surfacing in `FAILED` and summary counters.

## Success checks for Task 4.2
- `NEEDS_REVIEW` decreases on short-profile records without increasing false `OK` on single-energy-only inputs.
- `FAILED` remains semantically meaningful and now includes ingestion rejects.
- Parser warnings decrease for complete energy lines (`kJ + kcal`) while extraction values stay unchanged.
