import csv
import json
from pathlib import Path
from collections import Counter


def read_statuses(classified_path: Path):
    statuses = Counter()
    parser_warnings = Counter()
    reasons = Counter()
    rows = []
    if not classified_path.exists():
        return statuses, parser_warnings, reasons, rows
    with classified_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            rec = json.loads(line)
            rows.append(rec)
            statuses[rec.get("status", "")] += 1
            for warning in rec.get("parser_warnings", []) or []:
                parser_warnings[warning] += 1
            for reason in rec.get("status_reasons", []) or []:
                reasons[reason] += 1
    return statuses, parser_warnings, reasons, rows


def count_csv_rows(path: Path):
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def extract_log_line(path: Path, token: str):
    if not path.exists():
        return ""
    last = ""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if token in line:
            last = line
    return last


base_full = Path("tmp/out_task33_full")
new_full = Path("tmp/out_task42_full")
base_utf = Path("tmp/out_task24_utf")
new_utf = Path("tmp/out_task42_utf")

bf_s, bf_pw, bf_r, _ = read_statuses(base_full / "classified_records.jsonl")
nf_s, nf_pw, nf_r, _ = read_statuses(new_full / "classified_records.jsonl")

bu_s, bu_pw, bu_r, _ = read_statuses(base_utf / "classified_records.jsonl")
nu_s, nu_pw, nu_r, _ = read_statuses(new_utf / "classified_records.jsonl")

lines = []
lines.append("# Task 4.2 Comparison Evidence\n")
lines.append("## Full run delta (task32_input)\n")
lines.append(f"- Baseline statuses: {dict(bf_s)}")
lines.append(f"- New statuses: {dict(nf_s)}")
lines.append(f"- Baseline parser warnings: {dict(bf_pw)}")
lines.append(f"- New parser warnings: {dict(nf_pw)}")
lines.append(f"- Baseline status reasons: {dict(bf_r)}")
lines.append(f"- New status reasons: {dict(nf_r)}\n")

lines.append("## Ingestion-edge delta (utf fixture)\n")
lines.append(f"- Baseline statuses (classified records): {dict(bu_s)}")
lines.append(f"- New statuses (classified records): {dict(nu_s)}")
lines.append(f"- Baseline status reasons: {dict(bu_r)}")
lines.append(f"- New status reasons: {dict(nu_r)}")
lines.append(f"- Baseline failed.csv rows: {count_csv_rows(base_utf / 'failed.csv')}")
lines.append(f"- New failed.csv rows: {count_csv_rows(new_utf / 'failed.csv')}")
lines.append(f"- Baseline needs_review.csv rows: {count_csv_rows(base_utf / 'needs_review.csv')}")
lines.append(f"- New needs_review.csv rows: {count_csv_rows(new_utf / 'needs_review.csv')}\n")

lines.append("## Runtime summary evidence\n")
lines.append(f"- Baseline ingestion line: {extract_log_line(base_utf / 'run.log', 'CSV ingestion completed')}")
lines.append(f"- New ingestion line: {extract_log_line(new_utf / 'run.log', 'CSV ingestion completed')}")
lines.append(f"- New ingestion reject visibility line: {extract_log_line(new_utf / 'run.log', 'CSV ingestion reject visibility')}\n")

Path("tmp/task42_comparison_evidence.md").write_text("\n".join(lines), encoding="utf-8")
print("wrote tmp/task42_comparison_evidence.md")
