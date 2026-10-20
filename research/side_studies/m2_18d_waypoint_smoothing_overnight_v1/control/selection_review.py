"""Apply preregistered promotion and bounded-follow-up rules, without physics."""
from pathlib import Path
import json,time,copy,hashlib
import numpy as np
P=Path(__file__).resolve().parents[1]
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
data=json.loads((P/'ALL_ANALYZED_RESULTS.json').read_text());rows=data['rows'];eligible=[];signals=[];next_candidates=[]
for r in rows:
 if r['status']!='COMPLETE' or not r['candidate'].get('changes'):continue
 gates=r['task']=='PASS' and r['receipt']=='PASS' and r['safety'] and r['motion_pass'] and r['independent_audit']['status']=='PASS'
 duration_equal=r['comparison']['duration_abs_delta_s']<1e-8 and all(abs(x['duration_contribution_N_s'])<1e-8 for x in r['comparison']['symmetric_phase_decomposition'].values())
 force_route=r['full_J_F_delta']<=-.5
 motion_route=r['candidate']['base']=='E' and r['full_J_F_delta']<=.1 and r['full_TV_v_change_percent']<=-1 and r['full_jerk_change_percent']<=0
 nonzero=any(np.any(c['spec']['deltas_deg']) for c in r['candidate']['changes'])
 if gates and duration_equal and nonzero and (force_route or motion_route):eligible.append(dict(id=r['id'],force_route=force_route,motion_route=motion_route))
 if not r['candidate']['id'].endswith('_smooth'):continue
 local_signal=gates and all(loc['candidate']['TV_v']<=loc['baseline']['TV_v']*.995 and loc['candidate']['J_F']<loc['baseline']['J_F'] for loc in r['local'])
 signals.append(dict(id=r['id'],gates=gates,local_signal=local_signal,full_delta=r['full_J_F_delta'],full_TV_percent=r['full_TV_v_change_percent']))
 if local_signal:
  for kind,scale in [('half',.5),('repeat',1.)]:
   c=copy.deepcopy(r['candidate']);c['id']=c['id'].replace('_smooth','_'+kind)
   for ch in c['changes']:ch['spec']['deltas_deg']=(np.asarray(ch['spec']['deltas_deg'])*scale).tolist()
   next_candidates.append(c)
for base in ['B','E']:
 good=[r for r in rows if any(x['id']==r['id'] and x['local_signal'] for x in signals) and r['candidate']['base']==base]
 if len(good)==2:
  next_candidates.append(dict(id=base+'_OR_smooth',base=base,changes=sum([copy.deepcopy(r['candidate']['changes']) for r in good],[])))
out=dict(reviewed_unix=time.time(),promotion_rule_sha256=sha(P/'RUN_PLAN.json'),eligible=eligible,signals=signals,registered_followup_candidates=next_candidates,meaning='eligibility is development-only; no primary renamed and no heldout exposed',duration_rule='original duration gate retained; promotion additionally requires no task/phase duration advantage')
(P/'SELECTION_REVIEW.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
