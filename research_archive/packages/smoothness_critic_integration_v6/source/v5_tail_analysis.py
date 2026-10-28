"""Real rolling-tail labels, common-policy audit, and myopia trigger; no new physics."""
from pathlib import Path
import json,os,sys,hashlib
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
from scipy.stats import spearmanr,kendalltau
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def integral(t,x,lo,hi):
 dt=np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo));return float(np.linalg.norm(x[:-1],axis=1)@dt)
def group(name):
 c=json.loads((P/f'experiments/{name}.json').read_text());rows=[];dataset=[]
 for f in sorted((P/'attempts').glob(name+'_*_RESULT.json')):
  r=json.loads(f.read_text());ident=r['id'];cap=P/'history'/(ident+'_TAIL_CAUSAL.json')
  if not r['complete'] or not cap.exists():
   rows.append(dict(id=ident,complete=r['complete'],qualified=r['qualified'],error=r.get('error'),ranked=False));continue
  z=json.loads(cap.read_text());fork=z['fork_physical_s'];su=json.loads((P/'runtime/source/results'/ident/'summary.json').read_text())
  with np.load(P/'runtime/source/results'/ident/'trace.npz') as a:
   k=a['stage']=='TASK';t=a['time_s'][k];force=a['physical_cuff_force_world_n'][k];moment=a['physical_cuff_moment_world_nm'][k]
  fullJF=integral(t,force,fork,t[-1]);fullJM=integral(t,moment,fork,t[-1]);horizons={}
  for h,feat in z['captures'].items():
   split=feat['physical_s'];short=integral(t,force,fork,split);tail=integral(t,force,split,t[-1]);sm=integral(t,moment,fork,split);tm=integral(t,moment,split,t[-1]);assert abs(short+tail-fullJF)<1e-8 and abs(sm+tm-fullJM)<1e-8,'LEFT_QUADRATURE_TAIL_CLOSURE'
   labels=dict(short_JF=short,tail_JF=tail,full_remaining_JF=fullJF,short_JM=sm,tail_JM=tm,full_remaining_JM=fullJM,remaining_time_s=float(t[-1]-split));horizons[h]=labels
   dataset.append(dict(id=ident,parent_group=name,action=r['action'],qualified=r['qualified'],complete=True,parent_hash=z['fork_parent_hash'],horizon_s=float(h),feature_names=feat['feature_names'],features=feat['features'],causal_physical_s=split,labels=labels,truth_used_in_features=False,continuation_policy=z['continuation_policy']))
  intervention=[];continuation_bad=[]
  for lr in su['learning_records']:
   screen=lr.get('selected_plan',{}).get('execution_screen',{});sch=lr.get('selected_plan',{}).get('schedule') or {};ph=sch.get('phase');modal=screen.get('coordination_modal_v2');free=screen.get('free_trajectory')
   if modal or free or screen.get('second_round_posture') or screen.get('early_return_duration') or screen.get('terminal_hip_timing'):
    intervention.append(dict(decision_index=lr['decision_index'],phase=ph,request_time_s=lr['request_time_s'],modal=modal,free_parameters=None if free is None else free.get('parameters')))
    if lr['request_time_s']>fork+1e-8:continuation_bad.append(lr['decision_index'])
  assert not continuation_bad,'CONTINUATION_POLICY_POLLUTION:'+ident+':'+str(continuation_bad)
  rows.append(dict(id=ident,complete=True,qualified=r['qualified'],JF=r['JF'],JM=r['JM'],full_remaining_JF=fullJF,full_remaining_JM=fullJM,horizons=horizons,fork_physical_s=fork,parent_hash=z['fork_parent_hash'],intervention_records=intervention,continuation_audit='PASS: no T/modal/free/early/posture/timing intent in subsequent decision records',motion_failed=r['motion_vs_B']['failed_requirements']))
 complete=[r for r in rows if r['complete'] and 'horizons' in r];valid=[r for r in complete if r['qualified']];comparisons=[]
 for h in c['short_horizons_s']:
  use=[r for r in valid if str(h) in r['horizons']]
  if len(use)<2:continue
  short=np.array([r['horizons'][str(h)]['short_JF'] for r in use]);full=np.array([r['full_remaining_JF'] for r in use]);si=int(np.argmin(short));fi=int(np.argmin(full));regret=float(full[si]-full[fi]);spearman=float(spearmanr(short,full).statistic);kendall=float(kendalltau(short,full).statistic)
  comparisons.append(dict(horizon_s=h,qualified_candidates=len(use),short_choice=use[si]['id'],actual_full_tail_choice=use[fi]['id'],choices_differ=si!=fi,true_full_JF_regret_N_s=regret,short_choice_full_JM=use[si]['JM'],full_choice_full_JM=use[fi]['JM'],spearman=spearman if np.isfinite(spearman) else None,kendall=kendall if np.isfinite(kendall) else None,trigger=bool(si!=fi and regret>.02),rank_short=[use[i]['id'] for i in np.argsort(short)],rank_full=[use[i]['id'] for i in np.argsort(full)]))
 out=dict(group=name,condition=c['condition'],fork_phase=c['fork_phase'],fork_slot=c['fork_slot'],rows=rows,comparisons=comparisons,critic_gate_triggered=any(r['trigger'] for r in comparisons),gamma=1.,actual_remaining_cost_policy='original B rolling/replan after exactly one candidate decision',policy_audit='PASS',parent_hashes=sorted(set(r['parent_hash'] for r in complete)))
 put('analysis/tail/'+name+'.json',out);put('models/'+name+'_TAIL_LABELS.json',dataset)
 print('TAIL_GROUP',name,'complete',len(complete),'qualified',len(valid),'trigger',out['critic_gate_triggered'],'comparisons',comparisons,flush=True)
 return out
if __name__=='__main__':
 for n in sys.argv[1:] or ['TAILO1','TAILR1']:group(n)
