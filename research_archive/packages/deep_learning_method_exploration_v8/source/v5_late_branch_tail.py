"""Exploratory zero-physics tail diagnosis under the distinct fixed-modal follow policy."""
from pathlib import Path
import os,sys,json,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def integ(t,x,lo,hi):return float(np.linalg.norm(x[:-1],axis=1)@np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo)))
events=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];starts={r['id']:r for r in events if r['event']=='START'}
output=[]
for label,tags in [('FAIL9',['FAIL9','BLINDM9','BLINDP9']),('C19',['C19','BLINDMC19','BLINDPC19'])]:
 series=[];refs=[]
 for tag in tags:
  ident='BRANCH02_'+tag;r=json.loads((P/'attempts'/(ident+'_RESULT.json')).read_text());su=json.loads((P/'runtime/source/results'/ident/'summary.json').read_text());lr=next(x for x in su['learning_records'] if (m:=x.get('selected_plan',{}).get('execution_screen',{}).get('coordination_modal_v2')) and m['phase']=='RETURN' and m['slot']==1);cut=lr['request_time_s']
  changes=[x for x in su['learning_records'] if x.get('selected_plan',{}).get('execution_screen',{}).get('v5_blind_shift',{}).get('status')=='ACCEPTED']
  with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
   kk=z['stage']=='TASK';t=z['time_s'][kk];f=z['physical_cuff_force_world_n'][kk];m=z['physical_cuff_moment_world_nm'][kk];prefix={k:z[k][z['time_s']<=cut+1e-9].copy() for k in ['time_s','evaluation_only_human_state_rad_rad_s','estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','cr12_q_rad','cr12_dq_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm']}
  refs.append(prefix);series.append(dict(id=ident,qualified=r['qualified'],full_task_JF=r['JF'],full_task_JM=r['JM'],fork_time_s=cut,full_remaining_JF=integ(t,f,cut,t[-1]),full_remaining_JM=integ(t,m,cut,t[-1]),short_JF={str(H):integ(t,f,cut,cut+H) for H in [.25,.5,1.]},accepted_blind_intervention_count=len(changes),cold_parent_hash=starts[ident]['snapshot_hash']))
 same=all(all(np.array_equal(refs[0][k],x[k],equal_nan=True) for k in refs[0]) for x in refs[1:]);same_cut=max(x['fork_time_s'] for x in series)-min(x['fork_time_s'] for x in series)<1e-9;same_parent=len(set(r['cold_parent_hash'] for r in series))==1
 assert same and same_cut and same_parent,'LATE_BRANCH_COMMON_PREFIX_NOT_EXACT'
 assert all(r['accepted_blind_intervention_count']==(0 if i==0 else 1) for i,r in enumerate(series)),'NOT_A_SINGLE_BLIND_INTERVENTION'
 valid=[r for r in series if r['qualified']];best=min(valid,key=lambda r:r['full_remaining_JF']);comp=[]
 for H in [.25,.5,1.]:
  sh=min(series,key=lambda r:r['short_JF'][str(H)]);comp.append(dict(horizon_s=H,unmasked_short_choice=sh['id'],short_choice_original_qualified=sh['qualified'],actual_full_qualified_choice=best['id'],choice_changed=sh['id']!=best['id'],qualified_short_regret_N_s=sh['full_remaining_JF']-best['full_remaining_JF'] if sh['qualified'] else None,failed_short_choice_is_not_a_low_cost_success=not sh['qualified']))
 output.append(dict(case=label,rows=series,comparisons=comp,exact_recorded_causal_physical_prefix=True,common_initial_live_fork_parent_hash=True,distinct_following_policy='Original fixed '+label+' modal8_retimed plan applied through every subsequent actual rolling/replan decision. Blind microshift only at RETURN slot1.',state_identity_limit='No separate complete RAM hash was captured exactly at R1. Identical initial full-state live parent, deterministic identical controller prefix, exact recorded physical/reference prefix, common R1 request time and single-shift source logic support the comparison. This exploratory evidence does not replace the primary C1 full-live-state fork design.'))
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='EXPLORATORY_POSTHOC_NO_NEW_PHYSICS',rows=output,label_policy_separation='These tails follow a fixed modal policy, while the primary Critic uses original B after one action. Do not mix labels or infer the B-policy Critic failure probability from this study.',reason='A late guard/motion failure alone does not establish myopic choice; inspect the actual unmasked short-cost choice first.',new_physical_START=0)
(P/'analysis/LATE_BRANCH_POLICY_TAIL_DIAGNOSTIC.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for r in output:print(r['case'],r['comparisons'])
