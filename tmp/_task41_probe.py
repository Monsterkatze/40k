import csv
import os
import collections

base = 'tmp'
runs = ['out_task32', 'out_task33_full', 'out_task33_limit', 'out_task24_cp', 'out_task24_utf']

for run in runs:
    p = os.path.join(base, run)
    if not os.path.isdir(p):
        continue

    print(f"\n=== {run} ===")
    for name in ['report.csv', 'needs_review.csv', 'failed.csv']:
        f = os.path.join(p, name)
        if os.path.exists(f):
            with open(f, 'r', encoding='utf-8', newline='') as fh:
                rows = list(csv.DictReader(fh))
            print(name, 'rows=', len(rows), 'cols=', list(rows[0].keys())[:12] if rows else '[]')
            if rows:
                cols = rows[0].keys()
                for cand in ['status', 'reason', 'failure_reason', 'review_reason', 'error', 'notes', 'normalized_text', 'raw_text', 'category']:
                    if cand in cols:
                        cnt = collections.Counter((r.get(cand) or '').strip() for r in rows)
                        print(' top', cand, cnt.most_common(8))
        else:
            print(name, 'missing')

    lg = os.path.join(p, 'run.log')
    if os.path.exists(lg):
        with open(lg, 'r', encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
        hits = [ln.strip() for ln in lines if any(k in ln.lower() for k in ['summary', 'needs_review', 'failed', 'warning', 'error', 'completed', 'parsed', 'export'])]
        print(' run.log hits:', len(hits))
        for ln in hits[-10:]:
            print('  ', ln[:220])
    else:
        print(' run.log missing')
