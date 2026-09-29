"""Resumable execution of frozen refinement and cross-state validation plans."""
from __future__ import annotations
import argparse,json,os,subprocess,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
STAGE=Path(__file__).resolve().parents[2]
DOC=STAGE/'docs/safe_action_horizon_exploration_v1'
RUNS=STAGE/'results/safe_action_horizon_exploration_v1/runs'
RUNNER=Path(__file__).with_name('run_safe_action_horizon_rollout_v1.py')

def save(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    temp.replace(path)

def receipt(entry):
    path=RUNS/entry['run_id']/'rollout_result.json'
    return json.loads(path.read_text()) if path.exists() else None

def overall_counts():
    values=[]
    for path in RUNS.glob('*/rollout_result.json'):
        if path.parent.name.startswith(('coarse_','refine_','cross_')):
            values.append(json.loads(path.read_text()).get('status'))
    return Counter(values)

def progress(plan,phase):
    done=[(e,receipt(e)) for e in plan['entries']]
    done=[(e,r) for e,r in done if r is not None]
    current=Counter(r['status'] for _,r in done)
    total=overall_counts()
    result={'schema':'safe_action_horizon_plan_progress_v1','phase':phase,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'plan_count':len(plan['entries']),'plan_attempted':len(done),'plan_status_counts':dict(current),'total_attempted':sum(total.values()),'total_status_counts':dict(total),'last_run_id':done[-1][0]['run_id'] if done else None,'repair_cycles_used':2}
    save(DOC/'EXPLORATION_PROGRESS.json',result)
    save(DOC/(phase+'_PROGRESS.json'),result)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--max-new',type=int,default=100000)
    args=parser.parse_args()
    plan=json.loads(args.plan.read_text())
    if plan['status'] not in ('FROZEN_AFTER_COARSE_BEFORE_REFINEMENT','FROZEN_AFTER_REFINEMENT_BEFORE_CROSS_STATE') or len(plan['entries'])!=plan['candidate_count']:
        raise RuntimeError('plan is not frozen or has wrong length')
    phase='REFINEMENT' if 'REFINEMENT' in args.plan.name else 'CROSS_STATE'
    new=0
    for entry in plan['entries']:
        if receipt(entry) is not None:continue
        if new>=args.max_new:break
        command=[sys.executable,str(RUNNER),'--checkpoint-rep',str(entry['checkpoint_rep']),'--run-id',entry['run_id'],'--direction',entry['direction'],'--amplitude',entry['amplitude'],'--horizon',entry['horizon']]
        result=subprocess.run(command,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'},capture_output=True,text=True,timeout=600)
        new+=1
        state=progress(plan,phase)
        message={'plan_n':state['plan_attempted'],'plan_counts':state['plan_status_counts'],'total_n':state['total_attempted'],'run_id':entry['run_id'],'runner_stdout':result.stdout[-350:],'exit_code':result.returncode,'stderr_tail':result.stderr[-250:] if result.stderr else None}
        print(json.dumps(message),flush=True)
        log=STAGE/f'results/safe_action_horizon_exploration_v1/{phase.lower()}_orchestration.jsonl'
        log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('a') as f:f.write(json.dumps(message)+'\n')
        if receipt(entry) is None:
            print('INFRASTRUCTURE_NO_RECEIPT_REQUIRES_REPAIR',flush=True)
            break
        if state['plan_attempted']%25==0:
            save(DOC/(phase+'_ROLLS_CHECKPOINT.json'),[{**e,'status':receipt(e)['status']} for e in plan['entries'] if receipt(e) is not None])
        count=state['plan_status_counts'].get('EXCEPTION',0)
        if count>=10 and count>state['plan_attempted']*.5:
            print('SYSTEMIC_INFRASTRUCTURE_FAILURE_REQUIRES_REPAIR',flush=True)
            break
    print(json.dumps({'final_plan_progress':progress(plan,phase)}),flush=True)

if __name__=='__main__':main()
