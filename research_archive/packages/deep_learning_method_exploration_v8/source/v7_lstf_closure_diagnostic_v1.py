"""Original raw equivalence + unchanged LS terminal-factor label diagnostic."""
from pathlib import Path
import ast
import hashlib
import itertools
import json
import sys
import time
import numpy as np

P = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(P / 'runtime/code'))
from stream_runtime_evidence import array_items

dest = P / 'analysis/LSTF01_CLOSURE_AND_ALIAS_DIAGNOSTIC_V1.json'
assert not dest.exists()
source = P / 'runtime/control/base_campaign.py'
node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'compare_raw')
namespace = {'np': np, 'itertools': itertools, 'array_items': array_items}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(source), 'exec'), namespace)
a = P / 'runtime/source/results/LSTF01_T5F100'
b = P / 'runtime/source/results/LSTIM01_NO_T5'
equivalence = namespace['compare_raw'](a, b)
inputs = {str(source.relative_to(P)): hashlib.sha256(source.read_bytes()).hexdigest()}
for folder in [a, b]:
    for name in ['trace.npz', 'runtime_artifacts.json.gz', 'summary.json']:
        f = folder / name
        inputs[str(f.relative_to(P))] = hashlib.sha256(f.read_bytes()).hexdigest()
rows = []
for tag, factor in [('B', None), ('V6PHASE', 1.5), ('T5F100', 1.), ('T5F125', 1.25), ('T5F140', 1.4), ('T5F1475', 1.475)]:
    f = P / 'attempts' / ('LSTF01_' + tag + '_RESULT.json')
    r = json.loads(f.read_text())
    inputs[str(f.relative_to(P))] = hashlib.sha256(f.read_bytes()).hexdigest()
    m = r['motion_vs_B']
    rows.append({'id': r['id'], 'declared_terminal_factor': factor, 'complete': r['complete'],
                 'original_qualified': r['qualified'], 'JF': r['JF'], 'JM': r['JM'],
                 'failed_requirements': m['failed_requirements'], 'excursion_delta_deg_vs_B': m['excursion_delta_deg'],
                 'endpoint_abs_delta_deg': m['endpoint_abs_delta_deg'], 'formal_paired_success_vs_unqualified_phase': False})
result = {'status': 'COMPLETE_ORIGINAL_NEGATIVES_AND_ALIAS_RETAINED', 'created_unix': time.time(),
          'rows': rows, 'F100_vs_previous_NO_T5_original_compare_raw': equivalence,
          'F100_new_effective_physical_exploration': equivalence['status'] != 'PASS',
          'original_compare_function_AST_body_unmodified': True, 'no_base_campaign_module_import_side_effects': True,
          'new_fits': 0, 'new_env_model_physics': 0, 'threshold_or_task_change': False,
          'conclusion': 'All four legal factors remain original-unqualified; no independent validation launched. F100 alias, if confirmed, is fully charged and not counted as a new effective exploration.',
          'input_sha256': inputs, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with dest.open('x') as f:
    f.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print('LSTF_ALIAS', equivalence['status'])
for row in rows:
    print(row['id'], row['original_qualified'], row['excursion_delta_deg_vs_B'], row['failed_requirements'])
