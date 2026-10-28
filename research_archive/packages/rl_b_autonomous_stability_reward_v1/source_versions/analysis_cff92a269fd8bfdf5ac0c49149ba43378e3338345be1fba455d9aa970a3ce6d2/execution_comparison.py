"""Read-only causal execution comparison to original successful050 mean policy."""
from pathlib import Path
import sys,json,re,hashlib
from research_common import ROOT,RUNTIME,atomic,read,sha,now
sys.path.insert(0,str(RUNTIME))
from stream_json import array_items,read_evidence
import numpy as np
HISTORY=ROOT.parent/'rl_b_autonomous_replication_v1'

def read_json(p):
    with read_evidence(p,encoding='utf-8') as f:return json.load(f)
def short_native(raw,task_start):
    result={};prefix=hashlib.sha256();count=0
    for x in array_items(raw,'native_states_evaluation_only'):
        t=x['time_s'];physical=[x['qpos_evaluation_only'],x['qvel_evaluation_only'],x['command_torque_nm']]
        if t<=task_start+1e-9:
            prefix.update(json.dumps(physical,separators=(',',':')).encode());count+=1
        elif t<=task_start+.10000001:result[round((t-task_start)/.00025)]=x
        else:break
    return result,prefix.hexdigest(),count
def traces(raw):
    result={}
    for x in array_items(raw,'trace'):
        if x['stage']=='TASK':result[round(x['task_elapsed_s']/.00025)]=x
    return result
def first_difference(a,b,keys,threshold,transform=lambda x:x):
    for t in sorted(set(a)&set(b)):
        aa=transform(a[t][keys]);bb=transform(b[t][keys]);delta=float(np.max(np.abs(np.asarray(aa)-np.asarray(bb))))
        if delta>threshold:return dict(task_s=t*.00025,max_abs_difference=delta,parent=aa,candidate=bb,threshold=threshold)
    return None
def main():
    ev=[json.loads(x) for x in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()
         if json.loads(x)['mode']=='evaluation' and json.loads(x)['policy_mode']=='deterministic']
    parent_rows=[json.loads(x) for x in (HISTORY/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
    result=[]
    for seed in [1495656323,1630784693]:
        original=next(x for x in parent_rows if x['training_seed']==seed and x['kind']=='checkpoint050_first')
        parent_run=HISTORY/original['run'];parent_raw=parent_run/'env/episode_0001/runtime_artifacts.json'
        parent_info=read_json(parent_run/'env/episode_0001/episode_summary.json')
        start=parent_info['native_steps_total']*.00025-parent_info['task_s']
        pn,ph,pc=short_native(parent_raw,start);pt=traces(parent_raw)
        for x in ev:
            if x['seed']!=seed:continue
            run=Path(x['run']);raw=run/'env/episode_0001/runtime_artifacts.json'
            info=read_json(run/'env/episode_0001/episode_summary.json')
            start2=info['native_steps_total']*.00025-info['task_s']
            nn,nh,nc=short_native(raw,start2);nt=traces(raw)
            summary=read_json(run/'env/episode_0001/summary.json')
            failures=[d for d in summary['decisions'] if d.get('phase')=='RETURN' and d.get('activation_outcome')=='FAILED']
            margin=[]
            for d in failures:
                m=re.search(r'geometry \((-?[\d.]+) mm\)',d.get('planning_exception',''))
                if m:margin.append(float(m.group(1)))
            row=dict(job=x['job_id'],branch=x['branch'],seed=seed,checkpoint=x['parent'],success=x['success'],
                status=x['status'],abort_reason=x['abort_reason'],parent=str(parent_run),
                same_pre_TASK_physical_prefix=ph==nh and pc==nc,parent_prefix_native=pc,candidate_prefix_native=nc,
                parent_prefix_sha256=ph,candidate_prefix_sha256=nh,
                first_native_torque_difference=first_difference(pn,nn,'command_torque_nm',1e-8),
                first_native_Human_q_difference=first_difference(pn,nn,'qpos_evaluation_only',1e-9,lambda q:q[:2]),
                first_applied_reference_difference=first_difference(pt,nt,'q_ref_rad',1e-9),
                RETURN_planner_failures=failures,predicted_candidate_geometry_margins_mm=margin,
                actual_task_min_clearance_m=x['actual_human_motion']['native_true_physics']['minimum_clearance_m']['TASK'],
                actual_shank_bed_contact_steps=x['actual_human_motion']['native_true_physics']['shank_bed_contact_steps']['TASK'],
                interpretation='Candidate predicted geometry is distinct from actual physical clearance; FAILED at planner construction is not an activation-validator rejection.',
                physics_attempts=0,Adam_updates=0)
            result.append(row)
    atomic(ROOT/'audit/NEW_EXECUTION_CAUSAL_COMPARISON.json',dict(time_utc=now(),cases=result,
           category='SAVED_NATIVE_CAUSAL_COMPARISON_NO_NEW_PHYSICS',source_sha256=sha(Path(__file__)),
           limitation='Causal execution differences are established on nominal saved trajectories; does not identify the unique optimizer root cause.'))
    print('compared',len(result),'frozen mean trajectories; no new physics')
if __name__=='__main__':main()
