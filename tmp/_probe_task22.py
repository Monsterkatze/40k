import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nutrition_parser import parse_nutrition_fields

samples = [
    {
        'name': 'colon_style',
        'category': 'NUTRITION',
        'text': 'energie: 2294.00 kj; kcal: 548; fett: 12.5 g; davon gesaettigte fettsaeuren: 2.1 g',
    },
    {
        'name': 'slash_style',
        'category': 'NUTRITION',
        'text': 'fat/7.2g carbs/11.4 sugar/3.0 protein/8.1 salt/450 mg fiber/2',
    },
    {
        'name': 'tabular_like',
        'category': 'NUTRITION',
        'text': 'kohlenhydrate 31\tzucker 4\teiweiss 9\tsalz 800 mg',
    },
    {
        'name': 'mixed_with_marker',
        'category': 'MIXED',
        'text': 'zutaten: wasser, mehl. naehrwerte: energie 100 kj fett 1.5 kohlenhydrate 20 zucker 4',
    },
    {
        'name': 'mixed_first_signal',
        'category': 'MIXED',
        'text': 'zutaten wasser mehl allergene gluten energie 120 kj fett 3 carbs 4',
    },
    {
        'name': 'free_text_unreadable',
        'category': 'NUTRITION',
        'text': 'fat unknown sugar n/a protein ???',
    },
]

rows = []
for sample in samples:
    parsed = parse_nutrition_fields(sample['text'], sample['category'])
    rows.append({
        'name': sample['name'],
        'category': sample['category'],
        'input': sample['text'],
        'fields': parsed.fields,
        'warnings': list(parsed.warnings),
        'parse_basis': parsed.parse_basis,
    })

out_path = ROOT / 'tmp/task22_parser_probe.json'
out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
print(out_path)
