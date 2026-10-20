from pathlib import Path
import json,sys,os
import numpy as np
S=Path(__file__).resolve().parent.parent
def build():
 out=S/'LOCAL_EXECUTED_DECISIONS.jsonl';n=0
 with out.open('w') as f:
  for p in sorted((S/'output').glob('*_DATA.json')):
   d=json.loads(p.read_text());ident=d['id'];lp=S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');dp=S/'output'/(ident+'_DECISIONS.json');tp=S/'source/results'/ident/'trace.npz'
   if not d['metric']['task_valid'] or not all(x.exists() for x in [lp,dp,tp]):continue
   dec=json.loads(dp.read_text())['rows'];line=json.loads(lp.read_text())['rows']
   with np.load(tp) as z:
    ix=z['stage']=='TASK';t=z['time_s'][ix];force=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1)
   full=float(force[:-1]@np.diff(t))
   for r in line:
    if not r['selected_plan_activated'] or not r['actual_native_steps'] or r['proposal_physics_s'] is None:continue
    candidates=[v for v in dec if v['phase']==r['phase']]
    if not candidates:continue
    v=min(candidates,key=lambda v:abs(v['task_s']+t[0]-r['proposal_physics_s']));error=abs(v['task_s']+t[0]-r['proposal_physics_s'])
    if error>1e-6:continue
    now=r['proposal_physics_s'];dt=np.maximum(0,np.minimum(t[1:],now)-t[:-1]);prefix=float(force[:-1]@dt)
    captured=v.get('current_decision_input_contract');carry=(captured or {}).get('native_carry_schedule',{});complete=bool(captured and captured.get('capture_version',0)>=2 and (carry.get('type')=='NoneType' or carry.get('parameters',{}).get('coefficients') is not None))
    row=dict(source_run=ident,condition=d['condition'],parent_source=d['branch_start'],sample_kind='actual_executed_local_decision_with_observed_frozen_continuation',local_state_source='decision-time causal capture; not a durable full-state checkpoint',phase=v['phase'],native_index=v.get('native_index'),decision_physics_s=now,current_causal_input=captured,input_complete=complete,original_causal55D=v['observation'],action_input={k:v.get(k) for k in ['graph','registered_spec','action','raw_v2']},raw_v2_action_zero_placeholder_ignored=bool(v.get('raw_v2')),full_policy_reference=str(S/'CANDIDATE_CATALOG.json'),continuation='frozen rolling old Q' if ident.endswith('_Frozen_M2') else 'registered fixed table/PWL at remaining issued slots; B physical replanning/carry/fallback',label_only=dict(full_TASK_J_F_N_s=full,past_TASK_prefix_integral_N_s=prefix,remaining_TASK_J_F_N_s=full-prefix,native_realized_metadata=r['native_coordination_metadata'],executed_receipts_reference=str(lp),executed_native_steps=r['actual_native_steps']),integral_definition='original TASK left quadrature, every interval clipped at actual proposal time; no derivative-dedup indices',scope='observed continuation value, not single-step Q^B and not an independently matched local counterfactual',split_by=['Human','condition','parent_source','source_run'],no_future_label_in_current_input=True)
    f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n');n+=1
 return dict(rows=n,path=str(out),training_performed=False)
if __name__=='__main__':print(json.dumps(build()))
