from pathlib import Path
import sys,json,numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1')
sys.path.insert(0,str(P/'code'))
from stream_runtime_evidence import array_items
run=P/'source/results/interface2_B0'
z=np.load(run/'trace.npz');print('TRACE',[(k,z[k].shape) for k in z.files]);print('NATIVE',next(array_items(run/'runtime_artifacts.json.gz','native_states_evaluation_only')))
print('MULTI',json.loads((P/'output/interface2_knee_002_REFERENCE_OBJECTS.json').read_text())['references'].keys())
for name,r in json.loads((P/'output/interface2_knee_002_REFERENCE_OBJECTS.json').read_text())['references'].items():
 print('REF',r['duration_s'],r['knots_s'],r['binding'])
print('OLD18',list((P.parent/'ihear_overnight_research_retrospective_v1/motion_series').glob('*063*')))
