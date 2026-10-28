"""Counterfactual single-repetition replay from immutable V3 session checkpoints."""
from __future__ import annotations
import argparse, hashlib, json, os, platform, subprocess, sys, time, traceback
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
STAGE=ROOT/'stages/stage5_personalized_motion_learning'
for relative in ('stages/stage5_personalized_motion_learning/src','stages/stage4_adaptive_control/src','stages/stage3_full3d/src','stages/stage5_personalized_motion_learning/scripts/high_rom_v1'):
    sys.path.insert(0,str(ROOT/relative))
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import run_executed_case, advance_inter_rep_boundary, _jsonable
from traction_mpc_stage5.full3d_adaptive_integration_v1.session_state import zero_value_decision_rows
from zero_value_30rep_checkpoint import load_checkpoint
from baseline_accounting_v2 import task_wrench_cost
from baseline_acceptance_v2 import assess
from evaluate_execution_mode import evaluate
from summarize_phase_b import DOC

BASE=STAGE/'results/zero_value_30rep_baseline_v3/formal_session_01'
DOCBASE=STAGE/'docs/zero_value_30rep_baseline_v3'
CASE=STAGE/'configs/high_rom_v1/low_rom_regression_cases/balanced_ordinary_r01.json'
OPTIONS=STAGE/'configs/full3d_adaptive_integration_v1/autonomous_closed_loop_recovery_v1/incremental_clearance_terminal_v9.json'
RUNS=STAGE/'results/safe_action_horizon_exploration_v1/runs'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024): h.update(chunk)
    return h.hexdigest()

def save(path,value):
    path.write_text(json.dumps(_jsonable(value),indent=2,sort_keys=True,allow_nan=False)+'\n')

def classify_abort(summary):
    reason=str(summary.get('abort_reason') or '')
    return 'INFEASIBLE' if 'EXPLORATION_ACTION_INFEASIBLE' in reason or 'NO_FEASIBLE_WAYPOINT' in reason else 'INVALID'

def horizons(trace):
    mask=trace['stage']=='TASK'
    t=np.asarray(trace['time_s'][mask],dtype=float)
    force=np.linalg.norm(np.asarray(trace['physical_cuff_force_world_n'][mask],dtype=float),axis=1)
    phase=np.asarray(trace['task_phase'][mask])
    dt=np.diff(t)
    if not len(dt) or np.max(np.abs(dt-.005))>1e-9: raise ValueError('non-5ms task trace')
    interval=force[:-1]*dt
    def cost(m): return float(np.sum(interval[m]))
    return {'immediate_0p5s_n_s':cost((t[:-1]-t[0])<.5-1e-10),'short_1p5s_n_s':cost((t[:-1]-t[0])<1.5-1e-10),'outbound_n_s':cost(phase[:-1]=='OUTBOUND'),'hold_n_s':cost(phase[:-1]=='HOLD'),'return_n_s':cost(phase[:-1]=='RETURN'),'full_task_n_s':float(np.sum(interval)),'outbound_duration_s':float(np.sum(phase[:-1]=='OUTBOUND')*.005)}

def run(checkpoint_rep,run_id,direction=None,amplitude=None,horizon=None):
    if any(os.environ.get(x)!='1' for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')):
        raise RuntimeError('frozen scientific thread settings must each be 1')
    entry=next(x for x in json.loads((DOCBASE/'SESSION_CHECKPOINTS_MANIFEST_V3.json').read_text()) if x['repetition_index']==checkpoint_rep)
    cp=BASE/entry['path']
    if sha(cp)!=entry['sha256']: raise RuntimeError('source checkpoint hash mismatch')
    provenance_sha=sha(BASE/'session_provenance.json')
    if provenance_sha!=entry['provenance_sha256']: raise RuntimeError('source provenance hash mismatch')
    if sha(CASE)!=json.loads((STAGE/'docs/scientific_execution_architecture_v1/WSL_LEARNING_SCIENTIFIC_BASELINE.json').read_text())['configs']['low_rom_ordinary']['sha256']:
        raise RuntimeError('case differs from frozen WSL baseline')
    pattern=None if direction is None else {'direction':direction,'amplitude':amplitude,'horizon':horizon}
    if pattern is not None:
        import traction_mpc_stage5.full3d_adaptive_integration_v1.runtime as runtime_module
        from safe_action_horizon_adapter_v1 import ExplorationTerminalSetPlannerV1, SPEC_ENV, snapshot_exploration_task_call
        os.environ[SPEC_ENV]=json.dumps(pattern,sort_keys=True)
        runtime_module.TerminalSetHumanWaypointPlannerV1=ExplorationTerminalSetPlannerV1
        runtime_module.snapshot_task_call=snapshot_exploration_task_call
    out=RUNS/run_id
    out.mkdir(parents=True,exist_ok=False)
    rep=checkpoint_rep+1
    rep_dir=out/f'rep_{rep:02d}'
    official=json.loads((DOCBASE/'PER_REPETITION_V3.json').read_text())[checkpoint_rep]
    start=time.monotonic()
    record={'schema':'safe_action_horizon_rollout_v1','run_id':run_id,'source_checkpoint_repetition':checkpoint_rep,'target_repetition':rep,'source_checkpoint_sha256':entry['sha256'],'source_provenance_sha256':provenance_sha,'source_baseline_commit':'1f6308b820b64fc2cc7d8a01baa42e433835e68e','exploration_code_commit':subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip(),'python':sys.version,'host':platform.node(),'case_sha256':sha(CASE),'options_sha256':sha(OPTIONS),'execution_mode':'SCIENTIFIC_SIMULATION','action':{'kind':'matched_baseline_replay' if pattern is None else 'counterfactual_waypoint_perturbation','perturbation':pattern},'matched_baseline_J_F_task_n_s':official['J_F_task_n_s'],'baseline_human_model_sequence_at_task_start':official['human_model_at_task_start']['sequence'],'status':'RUNNING'}
    save(out/'rollout_result.json',record)
    try:
        context,rows=load_checkpoint(cp,entry['sha256'],provenance_sha)
        if len(rows)!=checkpoint_rep: raise RuntimeError('checkpoint repetition mismatch')
        boundary=advance_inter_rep_boundary(context,max_wait_s=2.0)
        save(out/'boundary_before.json',boundary)
        capture={}
        case=json.loads(CASE.read_text())
        options=json.loads(OPTIONS.read_text())
        summary=run_executed_case(rep_dir,qualification_case=case,qualification_arm='continual_adaptive',simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,autonomous_recovery_options=options,task_timeout_s=30.0,runtime_capture=capture,execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.0,session_context=context)
        launch={'schema':'high_rom_v1_development_case_result','case_key':case['case_key'],'case_sha256':sha(CASE),'options_sha256':sha(OPTIONS),'execution_mode':'SCIENTIFIC_SIMULATION','scientific_host_delay_ms':0.0,'plant_mode':'low_rom','session_id':run_id,'repetition_index':rep,'command':sys.argv,'status':summary['status'],'abort_reason':summary.get('abort_reason'),'elapsed_host_s':time.monotonic()-start}
        save(rep_dir/'HIGH_ROM_CASE_RESULT.json',launch)
        case_for_score={'case_key':case['case_key'],'physical_variant':case['cell']['family'],'candidate':case.get('coordination_candidate','low_rom_registered'),'path':str(CASE.relative_to(ROOT)),'sha256':sha(CASE)}
        mode=evaluate(rep_dir,case_for_score,json.loads((DOC/'PHASE_B_MATRIX.json').read_text())['scoring'],goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg'])
        save(rep_dir/'MODE_AWARE_RESULT_V2.json',mode)
        trace=np.load(rep_dir/'trace.npz')
        if summary['status']!='COMPLETE':
            record.update(status=classify_abort(summary),run_status=summary['status'],failure_reason=summary.get('abort_reason'),physical_validity=mode['physical_task_result']['status'],scientific_validity=mode['scientific_validity']['status'],gate_reasons=mode['physical_task_result']['reasons']+mode['scientific_validity']['reasons'],J_F_task_n_s=None,J_F_session_n_s=None,benefit_n_s=None,force_peak_n=None,moment_integral_nm_s=None,moment_peak_nm=None,minimum_deployable_clearance_m=summary['task'].get('minimum_session_clearance_m_deployable'),completion_time_s=summary['task']['physics_duration_s'],human_model_sequence_at_task_start=summary['commissioning']['handoff_belief']['sequence'],decision_count=len(summary['decisions']),partial_task_trace_available=True,matched_replay_pass=False if pattern is None else None)
        else:
            costs=task_wrench_cost(trace,trace['stage']=='TASK')
            decisions=zero_value_decision_rows(summary['decisions'])
            acceptance=assess(summary,mode,json.loads((rep_dir/'runtime_artifacts.json').read_text()),costs,decisions)
            h=horizons(trace)
            actual=costs['J_F_n_s']
            valid=acceptance['overall_baseline_scientific_result']=='PASS'
            record.update(status='VALID' if valid else 'INVALID',run_status=summary['status'],physical_validity=acceptance['physical_task_validity'],scientific_validity=acceptance['scientific_validity'],gate_reasons=acceptance['gate_reasons'],J_F_task_n_s=actual,J_F_session_n_s=actual+float(capture['runtime'].get('fresh_track_bootstrap',{}).get('cost',{}).get('J_F_n_s',0.0)),benefit_n_s=official['J_F_task_n_s']-actual if valid else None,force_peak_n=costs['peak_force_n'],moment_integral_nm_s=costs['moment_integral_nm_s'],moment_peak_nm=costs['peak_moment_nm'],minimum_deployable_clearance_m=summary['task'].get('minimum_session_clearance_m_deployable'),minimum_native_clearance_evaluation_only_m=summary['task'].get('minimum_true_physical_clearance_m_evaluation_only'),completion_time_s=summary['task']['physics_duration_s'],human_model_sequence_at_task_start=summary['commissioning']['handoff_belief']['sequence'],human_model_sequence_after=context['updater'].sequence,horizons=h,decision_count=len(summary['decisions']),matched_replay_abs_error_n_s=abs(actual-official['J_F_task_n_s']),matched_replay_pass=(valid and abs(actual-official['J_F_task_n_s'])<=1e-6) if pattern is None else None)
        record['exploration_executed_actions']=[{'phase':d.get('phase'),'label':d.get('executed_label'),'delta_q_rad':d.get('executed_action_delta_q_rad'),'source_state_rad_rad_s':d.get('deployable_state_rad_rad_s'),'reference_state_rad_rad_s':d.get('reference_state_rad_rad_s'),'target_q_rad':next((x.get('target_q_rad') for x in d.get('evaluations',[]) if x.get('label')==d.get('executed_label')),None)} for d in summary['decisions']]
        record['raw_files_sha256']={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='rollout_result.json'}
    except BaseException as error:
        record.update(status='EXCEPTION',failure_reason=f'{type(error).__name__}:{error}',traceback=traceback.format_exc()[-8000:])
    finally:
        record['elapsed_host_s']=time.monotonic()-start
        save(out/'rollout_result.json',record)
    print(json.dumps({k:record.get(k) for k in ('run_id','status','matched_replay_pass','J_F_task_n_s','matched_baseline_J_F_task_n_s','matched_replay_abs_error_n_s','failure_reason','gate_reasons','elapsed_host_s')}),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--checkpoint-rep',type=int,required=True,choices=[1,5,15,25])
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--direction',choices=['slower','faster','hip_leading','knee_leading','hip_dominant','knee_dominant'])
    ap.add_argument('--amplitude',choices=['very_small','small','fine_low','medium','fine_mid','fine_high','large'])
    ap.add_argument('--horizon',choices=['H1','H2','H3','H4'])
    args=ap.parse_args()
    if args.direction is not None and (args.amplitude is None or args.horizon is None):
        ap.error('amplitude and horizon are required with direction')
    run(args.checkpoint_rep,args.run_id,args.direction,args.amplitude,args.horizon)
