"""Evaluation-only native overshoot relative to unchanged public task targets."""
from pathlib import Path
import sys,json,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
P=Path(__file__).resolve().parents[1]
for group in sys.argv[1:]:
 C=json.loads((P/'experiments'/(group+'.json')).read_text());cp=P/C.get('case_path','runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json');case=json.loads(cp.read_text())
 for f in (P/'attempts').glob(group+'_*_RESULT.json'):
  r=json.loads(f.read_text())
  if not r['complete']:continue
  id=r['id'];su=json.loads((P/'runtime/source/results'/id/'summary.json').read_text());trans={r['to']:r['time_s'] for r in su['task']['phase_transitions']}
  with np.load(P/'runtime/motion_series'/(id+'.npz')) as z:t=z['time_s'];q=z['true_q_rad']
  out={}
  for ph,lo,hi,key,sign in [('OUTBOUND',t[0],trans['HOLD'],'goal_deg',1),('RETURN',trans['RETURN'],trans['COMPLETE'],'start_deg',-1)]:
   ix=(t>=lo-1e-9)&(t<=hi+1e-9);target=np.radians(case['task'][key]);out[ph]=np.degrees(np.maximum(0,np.max(sign*(q[ix]-target),axis=0))).tolist()
  d={'id':id,'native_terminal_overshoot_deg':out,'definition':'max(0,max(direction*(native actual q-original public phase goal))) for hip/knee; auxiliary metric, no original gate or raw change','case_sha256':__import__('hashlib').sha256(cp.read_bytes()).hexdigest()};dest=P/'analysis/overshoot'/(id+'.json');dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(d,indent=2)+'\n')
 print('OVERSHOOT_SAVED',group,flush=True)
