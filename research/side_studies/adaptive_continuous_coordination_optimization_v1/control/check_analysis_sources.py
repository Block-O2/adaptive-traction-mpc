from pathlib import Path
import ast,json
L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/adaptive_continuous_coordination_optimization_v1');P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1')
files=[]
for f in (L/'control').glob('*.py'):ast.parse(f.read_text());files.append(f.name)
(P/'audit/ANALYSIS_SOURCE_SYNTAX.json').write_text(json.dumps(dict(status='PASS',files=files),indent=2));print('ANALYSIS_AST_PASS',len(files))
