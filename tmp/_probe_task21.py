import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from text_normalization import normalize_nutrition_text

samples = [
    'Energie 2.294,00 kJ',
    'Fett\t\u00a03,50 g',
    '"Zucker" 12,4 g',
    'Protein 1,2,3 g',
]

out = []
for sample in samples:
    result = normalize_nutrition_text(sample)
    out.append({
        'input': sample,
        'normalized_text': result.normalized_text,
        'search_text': result.search_text,
        'tokens': list(result.tokens),
        'warnings': list(result.warnings),
    })

path = ROOT / 'tmp/task21_normalization_probe.json'
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(path)
