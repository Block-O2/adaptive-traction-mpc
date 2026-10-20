"""Resumable, balanced coarse grid across checkpoints, directions, scales, horizons."""
from __future__ import annotations
import argparse,csv,json,os,subprocess,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
STAGE=ROOT/'stages/stage5_personalized_motion_learning'
DOC=STAGE/'docs/safe_action_horizon_exploration_v1'
RUNS=STAGE/'results/safe_action_horizon_exploration_v1/runs'
RUNNER=Path(__file__).with_name('run_safe_action_horizon_rollout_v1.py')
PLAN=DOC/'COARSE_PLAN.json'
DIRECTIONS=('slower','faster','hip_leading','knee_leading','hip_dominant','knee_dominant')
HORIZONS=('H1','H2','H3','H4')
AMPLITUDES=('small','medium','large')
CHECKPOINTS=(1,5,15,25)

def save(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    temp.replace(path)

def make_plan():
    entries=[]
    for di,direction in enumerate(DIRECTIONS):
        for hi,horizon in enumerate(HORIZONS):
            for ci,cp in enumerate(CHECKPOINTS):
                amp=AMPLITUDES[(di+hi+ci)%3]
                entries.append({'run_id':f'coarse_{len(entries)+1:03d}_cp{cp:02d}_{direction}_{amp}_{horizon}','checkpoint_rep':cp,'direction':direction,'amplitude':amp,'horizon':horizon})
    for di,direction in enumerate(DIRECTIONS):
        for ci,cp in enumerate(CHECKPOINTS):
            amp=AMPLITUDES[(di+ci+1)%3]
            entries.append({'run_id':f'coarse_{len(entries)+1:03d}_cp{cp:02d}_{direction}_{amp}_H1','checkpoint_rep':cp,'direction':direction,'amplitude':amp,'horizon':'H1'})
    return {'schema':'safe_action_horizon_coarse_plan_v1','status':'FROZEN_BEFORE_COARSE_ROLLOUTS','entries':entries,'candidate_count':len(entries),'source_code_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()}

def rows(plan):
    out=[]
    for entry in plan['entries']:
        path=RUNS/entry['run_id']/'rollout_result.json'
        if not path.exists(): continue
        result=json.loads(path.read_text())
        item={**entry,'status':result['status'],'benefit_n_s':result.get('benefit_n_s'),'J_F_task_n_s':result.get('J_F_task_n_s'),'J_F_session_n_s':result.get('J_F_session_n_s'),'force_peak_n':result.get('force_peak_n'),'moment_peak_nm':result.get('moment_peak_nm'),'moment_integral_nm_s':result.get('moment_integral_nm_s'),'minimum_deployable_clearance_m':result.get('minimum_deployable_clearance_m'),'completion_time_s':result.get('completion_time_s'),'failure_reason':result.get('failure_reason'),'physical_validity':result.get('physical_validity'),'scientific_validity':result.get('scientific_validity'),'horizons':result.get('horizons'),'elapsed_host_s':result.get('elapsed_host_s')}
        out.append(item)
    return out

def progress(plan):
    done=rows(plan)
    counts=Counter(x['status'] for x in done)
    state={'schema':'safe_action_horizon_progress_v1','phase':'COARSE','timestamp_utc':datetime.now(timezone.utc).isoformat(),'planned':len(plan['entries']),'attempted':len(done),'valid':counts['VALID'],'infeasible':counts['INFEASIBLE'],'invalid':counts['INVALID'],'exception':counts['EXCEPTION'],'last_run_id':done[-1]['run_id'] if done else None,'repair_cycles_used':2,'source_baseline_commit':'1f6308b820b64fc2cc7d8a01baa42e433835e68e'}
    save(DOC/'EXPLORATION_PROGRESS.json',state)
    return state

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--max-new',type=int,default=100000)
    args=ap.parse_args()
    DOC.mkdir(parents=True,exist_ok=True)
    if not PLAN.exists(): save(PLAN,make_plan())
    plan=json.loads(PLAN.read_text())
    if plan['candidate_count']!=120: raise RuntimeError('coarse plan changed')
    new=0
    for entry in plan['entries']:
        existing=RUNS/entry['run_id']/'rollout_result.json'
        if existing.exists(): continue
        if new>=args.max_new: break
        command=[sys.executable,str(RUNNER),'--checkpoint-rep',str(entry['checkpoint_rep']),'--run-id',entry['run_id'],'--direction',entry['direction'],'--amplitude',entry['amplitude'],'--horizon',entry['horizon']]
        result=subprocess.run(command,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'},capture_output=True,text=True,timeout=600)
        new+=1
        state=progress(plan)
        print(json.dumps({'n':state['attempted'],'valid':state['valid'],'infeasible':state['infeasible'],'invalid':state['invalid'],'exception':state['exception'],'run_id':entry['run_id'],'runner_stdout':result.stdout.strip()[-600:],'process_exit_code':result.returncode,'process_stderr_tail':result.stderr[-300:] if result.stderr else None}),flush=True)
        if state['attempted']%25==0 or state['attempted']==len(plan['entries']):
            save(DOC/'ALL_EXPLORATORY_ROLLOUTS.json',rows(plan))
        if state['exception']>=10 and state['exception']>state['attempted']*.5:
            print('SYSTEMIC_INFRASTRUCTURE_FAILURE_REQUIRES_REPAIR',flush=True)
            break
    state=progress(plan)
    save(DOC/'ALL_EXPLORATORY_ROLLOUTS.json',rows(plan))
    print(json.dumps({'coarse_state':state}),flush=True)

if __name__=='__main__':main()
