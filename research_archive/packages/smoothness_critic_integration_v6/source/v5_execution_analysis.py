from pathlib import Path
import os,sys,json,collections,hashlib
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if hasattr(x,'tolist'):return clean(x.tolist())
 return x
def analyze(ident):
 r=json.loads((P/'attempts'/(ident+'_RESULT.json')).read_text())
 if not r['complete']:return None
 su=json.loads((P/'runtime/source/results'/ident/'summary.json').read_text());rows=[]
 for lr in su['learning_records']:
  plan=lr.get('selected_plan',{});screen=plan.get('execution_screen',{});sch=plan.get('schedule') or {};smooth=screen.get('v5_reference_smooth');ant=screen.get('v5_anticipatory')
  rows.append(dict(decision_index=lr['decision_index'],request_time_s=lr['request_time_s'],accepted_schedule=sch,activated=lr.get('selected_plan_activated'),actual_reference_start_s=lr.get('start_time_s'),actual_reference_end_s=lr.get('end_time_s'),smooth=smooth,anticipatory=ant,original_modal=screen.get('coordination_modal_v2'),candidate_rejections=[dict(label=a.get('label'),reason=a.get('rejection_reason')) for a in lr.get('candidate_set',[]) if a.get('feasible') is False]))
 sm=[x['smooth'] for x in rows if x['smooth']];an=[x['anticipatory'] for x in rows if x['anticipatory']];changed=[x for x in rows if x['anticipatory'] and x['anticipatory']['changed']]
 out=dict(id=ident,qualified=r['qualified'],source_summary_sha256=hashlib.sha256((P/'runtime/source/results'/ident/'summary.json').read_bytes()).hexdigest(),smooth_proposed=len(sm),smooth_accepted=sum(x['status']=='ACCEPTED' for x in sm),smooth_rejection_reasons=dict(collections.Counter(x.get('reason') for x in sm if x['status']!='ACCEPTED')),local_reference_jerk_energy_original_sum=float(sum(np.sum(x['original_reference_jerk_energy']) for x in sm)),local_reference_jerk_energy_proposed_sum=float(sum(np.sum(x['proposed_reference_jerk_energy']) for x in sm)),anticipation_decisions=len(an),anticipation_changed=len(changed),anticipation_changed_and_activated=sum(bool(x['activated']) for x in changed),minimum_predicted_lookahead_s=min((x['anticipatory']['selected_risk']['predicted_event_local_s'] for x in changed),default=None),guard_replaced=False,rows=rows,meaning='Optimization inputs and candidate menu frozen before activation; actual activated signed schedule shown separately from proposed changes. Local reference-jerk sum is not full realized reference or Human jerk.')
 f=P/'analysis/execution'/(ident+'.json');f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(clean(out),ensure_ascii=False,indent=2)+'\n');print('EXECUTION',ident,'smooth accepted',out['smooth_accepted'],'/',out['smooth_proposed'],'anticipation changed',out['anticipation_changed_and_activated'],flush=True);return out
if __name__=='__main__':
 for ident in sys.argv[1:] or [f.name[:-12] for f in sorted((P/'attempts').glob('*_RESULT.json'))]:analyze(ident)
