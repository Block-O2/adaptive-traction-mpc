from pathlib import Path
import json,os,sys,shutil
import numpy as np
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
rows=json.loads((P/'derived/PREDICTION_TERMINAL_ROWS.json').read_text());summary=[]
for method in sorted(set(r['method'] for r in rows)):
 for h in [.04,.1,.2]:
  rr=[r for r in rows if r['arm']=='ER' and r['method']==method and abs(r['horizon_s']-h)<1e-8 and r['origin_task_s']<16.5085 and r['origin_task_s']+h<=16.9]
  alarms=[r for r in rr if r['prediction_deg_deg_s'][1]<9.5]
  summary.append(dict(method=method,horizon_s=h,origins=len(rr),first_predicted_below_goal_origin_s=min([r['origin_task_s'] for r in alarms],default=None),true_crossing_task_s=16.5085,lead_s=(16.5085-min(r['origin_task_s'] for r in alarms)) if alarms else None,false_positive_count=sum(r['truth_deg_deg_s'][1]>=9.5 for r in alarms),true_positive_count=sum(r['truth_deg_deg_s'][1]<9.5 for r in alarms)))
out=dict(scope='Development trajectory causal forecasting, no fitted predictor or action selected from future truth',rows=summary,decision='Local sensed-wrench model can indicate an approaching crossing on this development trace. It is not a closed-loop action-response predictor and has no held-out uncertainty calibration; do not use it to optimize small terminal compensation as if certified. Test hip timing and bounded existing-control/PD/FF through full physics.',gap_comparison='W1 excursion deficit0.048596467deg; 100ms sensed-wrench terminal p95 q error0.074371757deg is larger; this comparison rejects precision certification, not all predictive usefulness.',constant_acceleration='Causal observed acceleration baseline is competitive; no evidence that complexity of current model brings robust incremental predictive benefit at100ms.')
(P/'derived/PREDICTION_DECISION.json').write_text(json.dumps(out,indent=2)+'\n');dst=R/'derived/PREDICTION_DECISION.json';dst.parent.mkdir(exist_ok=True);shutil.copy2(P/'derived/PREDICTION_DECISION.json',dst)
print(json.dumps(out))
