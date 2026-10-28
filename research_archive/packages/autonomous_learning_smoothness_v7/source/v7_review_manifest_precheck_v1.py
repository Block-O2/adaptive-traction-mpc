"""Read-only compatibility/content precheck of already sealed review outputs."""
from pathlib import Path
import ast
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
dest = P / 'audit/REVIEW_MANIFEST_CONTENT_PRECHECK_V1.json'
assert not dest.exists()
source = P / 'agent_reviews/final_verifier/verify_final_package.py'
node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'manifest_rows')
namespace = {}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), 'exec'), namespace)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(2**20), b''):
            h.update(b)
    return h.hexdigest()


inventory = json.loads((P / 'agent_reviews/final_metadata_inventory/REVIEW_INVENTORY_CANDIDATE.json').read_text())
rows, errors = [], []
for review in inventory['agent_reviews']:
    directory = P / review['directory']
    mp, ep = P / review['manifest'], P / review['end']
    item = {'directory': review['directory'], 'manifest': review['manifest'], 'end': review['end'],
            'manifest_sha256': sha(mp), 'end_sha256': sha(ep), 'checked': 0, 'errors': []}
    try:
        manifest = json.loads(mp.read_text())
        for rel, expected in namespace['manifest_rows'](manifest):
            if not expected:
                continue
            f = Path(rel) if Path(rel).is_absolute() else directory / rel
            if not f.exists():
                item['errors'].append({'file': str(f), 'error': 'MISSING'})
            elif sha(f) != expected:
                item['errors'].append({'file': str(f), 'error': 'HASH_CHANGED', 'expected': expected, 'actual': sha(f)})
            item['checked'] += 1
    except Exception as error:
        item['errors'].append({'error': type(error).__name__ + ':' + str(error)})
    rows.append(item)
    errors.extend(item['errors'])
    print('REVIEW_OUTPUTS', directory.name, item['checked'], len(item['errors']), flush=True)
result = {'status': 'PASS' if not errors else 'MISMATCHES_PRESERVED_NOT_REPAIRED', 'created_unix': time.time(),
          'rows': rows, 'errors': errors, 'scope': 'Thirty originally compatible sealed review manifests only; no actual final package/ownership/scoring audit.',
          'source_sha256': sha(Path(__file__)), 'original_manifest_rows_source_sha256': sha(source),
          'new_env_model_fit_physics': 0}
with dest.open('x') as f:
    f.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print('REVIEW_OUTPUT_PRECHECK', result['status'], len(rows), len(errors), flush=True)
