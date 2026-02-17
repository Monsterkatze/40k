# Task 1.4 Audit Report - Baseline Metrics

## Scope
- Classified records analyzed: **4**
- Input artifacts: tmp/out_task13_cp/classified_records.jsonl, tmp/out_task13_utf/classified_records.jsonl

## Category Distribution
- MISSING: 0 (0.0%)
- INGREDIENTS: 0 (0.0%)
- NUTRITION: 4 (100.0%)
- MIXED: 0 (0.0%)
- UNKNOWN: 0 (0.0%)

## Dominant Diagnostic Patterns
- rule_applied=nutrition_min2: 4

## Problem Clusters
- UNKNOWN samples: None observed
- MIXED ambiguity samples: None observed
- Weak nutrition evidence (<2 nutrition signals): None observed
- Encoding-affected/malformed in classified data: None observed
- Encoding-related runtime evidence (logs):
  - [tmp/out_task13_cp/run.log] 2026-02-13 08:38:20 | WARNING | Encoding 'utf-8-sig' failed with decode error: 'utf-8' codec can't decode byte 0xc3 in position 23: invalid continuation byte
  - [tmp/out_task13_cp/run.log] 2026-02-13 08:38:20 | INFO | CSV ingestion started with encoding=cp1252 header_map={'id': 'ArtikelID', 'name': 'Bezeichnung', 'nutrition_raw_text': 'NÃhrwerte'}

## Parser Prioritization Baseline (Phase 2)
- Priority 1: Expand fixture coverage to force non-NUTRITION categories (UNKNOWN, MIXED, INGREDIENTS, MISSING) for measurable parser tuning.
- Priority 2: Add malformed/mojibake nutrition text fixtures to quantify normalization robustness impact on signals.
- Priority 3: Track weak-signal edge cases where ingredient markers co-occur with only one nutrition signal (tie-break sensitivity).

## Determinism Note
- This baseline is reproducible from the listed artifacts and deterministic classification rules in cell_classification.py.
