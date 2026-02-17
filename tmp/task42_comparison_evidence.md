# Task 4.2 Comparison Evidence

## Full run delta (task32_input)

- Baseline statuses: {'OK_WITH_WARNINGS': 2, 'NEEDS_REVIEW': 1}
- New statuses: {'OK': 2, 'NEEDS_REVIEW': 1}
- Baseline parser warnings: {'unreadable_field:kcal': 2}
- New parser warnings: {}
- Baseline status reasons: {'warnings_present': 2, 'insufficient_parsed_fields:1<3': 1}
- New status reasons: {'all_checks_passed': 2, 'minimal_profile_energy_only': 1}

## Ingestion-edge delta (utf fixture)

- Baseline statuses (classified records): {'NEEDS_REVIEW': 2}
- New statuses (classified records): {'OK_WITH_WARNINGS': 1, 'NEEDS_REVIEW': 1}
- Baseline status reasons: {'insufficient_parsed_fields:2<3': 1, 'insufficient_parsed_fields:1<3': 1}
- New status reasons: {'minimal_profile_ok': 1, 'minimal_profile_energy_only': 1}
- Baseline failed.csv rows: 0
- New failed.csv rows: 3
- Baseline needs_review.csv rows: 2
- New needs_review.csv rows: 1

## Runtime summary evidence

- Baseline ingestion line: 2026-02-13 09:02:56 | INFO | CSV ingestion completed | encoding=utf-8-sig total=5 valid=2 skipped=3
- New ingestion line: 2026-02-13 09:27:52 | INFO | CSV ingestion completed | encoding=utf-8-sig total=5 valid=2 skipped=3
- New ingestion reject visibility line: 2026-02-13 09:27:52 | INFO | CSV ingestion reject visibility | surfaced_failed_rows=3
