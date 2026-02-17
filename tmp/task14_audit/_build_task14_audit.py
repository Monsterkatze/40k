import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(r"c:\Users\User\Documents\40k")
classified_paths = sorted(ROOT.glob("tmp/out_task13_*/classified_records.jsonl"))
runlog_paths = sorted(ROOT.glob("tmp/out_task13_*/run.log"))
category_order = ["MISSING", "INGREDIENTS", "NUTRITION", "MIXED", "UNKNOWN"]

records = []
for path in classified_paths:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["_source"] = str(path.relative_to(ROOT)).replace("\\", "/")
            records.append(rec)

total = len(records)
category_counts = Counter(r.get("category", "UNKNOWN") for r in records)
category_distribution = {}
for c in category_order:
    n = category_counts.get(c, 0)
    pct = round((n / total * 100.0), 2) if total else 0.0
    category_distribution[c] = {"count": n, "pct": pct}

rule_counts = Counter((r.get("diagnostics") or {}).get("rule_applied", "unknown_rule") for r in records)
combo_counts = Counter(
    tuple((r.get("diagnostics") or {}).get("nutrition_signals", []))
    for r in records
)

unknown_records = [
    {
        "product_id": r.get("product_id"),
        "row_number": r.get("row_number"),
        "source": r.get("_source"),
        "snippet": (r.get("nutrition_raw_text") or "")[:120],
    }
    for r in records if r.get("category") == "UNKNOWN"
][:5]

mixed_records = [
    {
        "product_id": r.get("product_id"),
        "row_number": r.get("row_number"),
        "source": r.get("_source"),
        "snippet": (r.get("nutrition_raw_text") or "")[:120],
        "ingredient_signals": (r.get("diagnostics") or {}).get("ingredient_signals", []),
        "nutrition_signals": (r.get("diagnostics") or {}).get("nutrition_signals", []),
    }
    for r in records if r.get("category") == "MIXED"
][:5]

weak_nutrition_records = [
    {
        "product_id": r.get("product_id"),
        "row_number": r.get("row_number"),
        "source": r.get("_source"),
        "snippet": (r.get("nutrition_raw_text") or "")[:120],
        "nutrition_signal_count": (r.get("diagnostics") or {}).get("nutrition_signal_count", 0),
        "nutrition_signals": (r.get("diagnostics") or {}).get("nutrition_signals", []),
    }
    for r in records
    if (r.get("diagnostics") or {}).get("nutrition_signal_count", 0) < 2
][:5]

mojibake_re = re.compile(r"[ÃÂ]")
encoding_affected_data = [
    {
        "product_id": r.get("product_id"),
        "row_number": r.get("row_number"),
        "source": r.get("_source"),
        "snippet": (r.get("nutrition_raw_text") or "")[:120],
    }
    for r in records if mojibake_re.search(r.get("nutrition_raw_text") or "")
][:5]

encoding_log_lines = []
for p in runlog_paths:
    rel = str(p.relative_to(ROOT)).replace("\\", "/")
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if "Encoding 'utf-8-sig' failed" in line or "NÃhrwerte" in line:
                encoding_log_lines.append({"source": rel, "line": line})

metrics = {
    "task_ref": "Task 1.4 - Audit Report & Baseline Metrics",
    "source_classified_files": [str(p.relative_to(ROOT)).replace("\\", "/") for p in classified_paths],
    "source_run_logs": [str(p.relative_to(ROOT)).replace("\\", "/") for p in runlog_paths],
    "record_count": total,
    "category_distribution": category_distribution,
    "rule_applied_distribution": dict(sorted(rule_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
    "top_nutrition_signal_combinations": [
        {"signals": list(k), "count": v}
        for k, v in sorted(combo_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    ],
    "clusters": {
        "unknown_samples": unknown_records,
        "mixed_samples": mixed_records,
        "weak_nutrition_samples": weak_nutrition_records,
        "encoding_affected_data_samples": encoding_affected_data,
        "encoding_affected_log_evidence": encoding_log_lines[:8],
    },
    "interpretation_notes": [
        "Current ingestion-gated flow skips rows with empty nutrition_raw_text before classification, so MISSING may remain zero in baseline.",
        "Baseline is deterministic: category assignment depends only on static signal sets and priority logic.",
    ],
}

out_json = ROOT / "tmp/task14_audit/baseline_metrics.json"
out_md = ROOT / "tmp/task14_audit/audit_report_task14.md"
out_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

lines = []
lines.append("# Task 1.4 Audit Report - Baseline Metrics")
lines.append("")
lines.append("## Scope")
lines.append(f"- Classified records analyzed: **{total}**")
lines.append(f"- Input artifacts: {', '.join(metrics['source_classified_files']) if metrics['source_classified_files'] else 'None'}")
lines.append("")
lines.append("## Category Distribution")
for c in category_order:
    item = category_distribution[c]
    lines.append(f"- {c}: {item['count']} ({item['pct']}%)")
lines.append("")
lines.append("## Dominant Diagnostic Patterns")
if metrics["rule_applied_distribution"]:
    for rule, cnt in metrics["rule_applied_distribution"].items():
        lines.append(f"- rule_applied={rule}: {cnt}")
else:
    lines.append("- No classified records available.")
lines.append("")
lines.append("## Problem Clusters")
lines.append("- UNKNOWN samples: " + ("None observed" if not unknown_records else str(unknown_records)))
lines.append("- MIXED ambiguity samples: " + ("None observed" if not mixed_records else str(mixed_records)))
lines.append("- Weak nutrition evidence (<2 nutrition signals): " + ("None observed" if not weak_nutrition_records else str(weak_nutrition_records)))
if encoding_affected_data:
    lines.append("- Encoding-affected/malformed in classified data: " + str(encoding_affected_data))
else:
    lines.append("- Encoding-affected/malformed in classified data: None observed")
if encoding_log_lines:
    lines.append("- Encoding-related runtime evidence (logs):")
    for row in encoding_log_lines[:5]:
        lines.append(f"  - [{row['source']}] {row['line']}")
else:
    lines.append("- Encoding-related runtime evidence (logs): None")
lines.append("")
lines.append("## Parser Prioritization Baseline (Phase 2)")
lines.append("- Priority 1: Expand fixture coverage to force non-NUTRITION categories (UNKNOWN, MIXED, INGREDIENTS, MISSING) for measurable parser tuning.")
lines.append("- Priority 2: Add malformed/mojibake nutrition text fixtures to quantify normalization robustness impact on signals.")
lines.append("- Priority 3: Track weak-signal edge cases where ingredient markers co-occur with only one nutrition signal (tie-break sensitivity).")
lines.append("")
lines.append("## Determinism Note")
lines.append("- This baseline is reproducible from the listed artifacts and deterministic classification rules in cell_classification.py.")

out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"WROTE:{out_json}")
print(f"WROTE:{out_md}")
