"""Nonphysical software checks; synthetic data never enters scientific results."""
from pathlib import Path
import sys,ast,json,time,hashlib,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
sys.path.insert(0,str(R/'learning'))
import numpy as np
from value_model import fit,predict,choose
files=[f for folder in ['control','analysis','learning'] for f in (R/folder).glob('*.py')]
for f in files:ast.parse(f.read_text(),filename=str(f))
x=np.array([[-2.],[-1.],[1.],[2.]])
y=np.c_[np.zeros(4),x[:,0],-x[:,0],np.ones(4)]
m=fit(x,y,.001);pred=predict(m,np.array([[-1.],[1.]]))
assert pred.argmin(1).tolist()==[1,2],'STATE_ACTION_INTERACTION_BROKEN'
assert choose(np.array([0.,-2.,-1.,1.]),np.ones((4,3)),np.ones(4)*.1,np.zeros((4,3)))==1
assert choose(np.array([0.,-2.,-1.,1.]),-np.ones((4,3)),np.ones(4)*.1,np.zeros((4,3)))==0
assert choose(np.array([0.,-.01,-.02,1.]),np.ones((4,3)),np.ones(4)*.1,np.zeros((4,3)))==0
repair_margin=np.ones((4,3));repair_margin[0]=-1;repair_margin[1:3]=-1
assert choose(np.array([0.,.3,.4,1.]),repair_margin,np.ones(4)*.1,np.zeros((4,3)))==3
online=[]
for name in ['causal_features.py','frozen_selector.py','feedback_selector.py','early_features.py','early_selector.py']:
    source=(R/'control'/name).read_text()
    assert 'qpos' not in source and 'qvel' not in source and 'source/results' not in source and '/reports' not in source
    online.append(dict(file=name,sha256=hashlib.sha256(source.encode()).hexdigest(),manual_input_contract='Only current causal state and frozen model; feedback selector also reads immutable completed-task measured feedback',forbidden_truth_raw_access_tokens=False))
(P/'audit'/('ANALYSIS_CODE_CHECKS_'+str(int(time.time()))+'.json')).write_text(json.dumps(dict(status='PASS',unix=time.time(),AST_files=len(files),synthetic_state_action_crossing=True,guard_failure_fallback=True,guard_uncertainty_fallback=True,predicted_qualification_recovery=True,synthetic_data_role='software test only, never in dataset/models or scientific performance claims',online_source_checks=online,new_physics_starts=0),indent=2)+'\n')
print('NONPHYSICAL_CODE_CHECKS_PASS',len(files),flush=True)
