from pathlib import Path
import json,ast,itertools,importlib.util,numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
sp=importlib.util.spec_from_file_location('raw_arithmetic',P/'control/independent_recompute.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
tree=ast.parse((P/'control/base_campaign.py').read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw');ns=dict(np=np,itertools=itertools,array_items=a.array_items);exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen_field_comparison','exec'),ns)
check=ns['compare_raw'](P/'source/results/refine_P_corridor',P/'source/results/repeat_P_corridor');assert check['status']=='PASS'
(P/'audit/CROSS_BATCH_REPEAT.json').write_text(json.dumps(check,indent=2)+'\n');print('CROSS_BATCH_FULL_RAW_REPEAT_PASS',flush=True)
