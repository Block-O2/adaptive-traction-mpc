"""Use unchanged scorer-v2 physical predicates; new activation records audited explicitly."""
from pathlib import Path
import sys,json,gzip,tempfile,shutil,hashlib
import numpy as np
R=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1/source');S=R/'stages/stage5_personalized_motion_learning';D=S/'docs/adaptive_human_online_interface_v1'
sys.path.insert(0,str(S/'scripts/high_rom_v1'))
from summarize_phase_b import score
from evaluate_execution_mode import evaluate
def load(p):return json.loads(p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read())
def main():
    scoring=load(S/'docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring'];contract=load(D/'EXPERIMENT_CONTRACT.json');rows=[]
    paths=list((S/'results/adaptive_human_online_interface_v1/human').glob('*/qualification.json'))+list((S/'results/adaptive_human_online_interface_v1/online').glob('*/result.json'))
    inputs=[(p.parent,load(p)) for p in paths]
    gym_path=D/'DIRECT_RL_GYM_READINESS.json'
    if gym_path.exists():
        for record in load(gym_path)['runs']:
            for path in (S/'results/adaptive_human_online_interface_v1/gym'/record['pattern']).glob('episode_*'):
                inputs.append((path,dict(status=record['status'],elapsed_host_s=record['host_s'])))
    for path,row in inputs:
        if row.get('completion',row.get('status'))=='EXCEPTION' or not (path/'trace.npz').exists():continue
        case_info=next(x for x in contract['cases'] if x['id']==row.get('condition','high_rom_nominal_sync_120_v1'))
        case=case_info['case'];s=load(path/'summary.json');a=load(path/'runtime_artifacts.json')
        with tempfile.TemporaryDirectory(prefix='scorer_',dir=S/'results/adaptive_human_online_interface_v1') as temp:
            p=Path(temp)
            for name,value in (('summary.json',s),('runtime_artifacts.json',a),('HIGH_ROM_CASE_RESULT.json',dict(status=s['status'],abort_reason=s.get('abort_reason'),case_sha256=case_info['sha256'],elapsed_host_s=row['elapsed_host_s'],execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_ms=0.))):(p/name).write_text(json.dumps(value))
            (p/'trace.npz').symlink_to(path/'trace.npz')
            mode=evaluate(p,dict(case_key=case['case_key'],physical_variant=case['cell']['family'],candidate=case.get('coordination_candidate'),path=case_info['path'],sha256=case_info['sha256']),scoring,goal_deg=case['task']['goal_deg'],start_deg=case['task']['start_deg'])
            result=mode['raw_scorer_v2']
        physical={k:v for k,v in result.get('conditions',{}).items() if k!='plan_age'}
        online=s.get('online_reference_records',[]);accepted=[x for x in online if x.get('status')=='ACCEPTED']
        certs=all(x['activation_validation']['feasible'] and x['activation_validation']['C2'] and not x['activation_validation']['truth_consumed'] for x in accepted)
        new_cert_nonvacuous=(not online or bool(accepted))
        finite_native=all(np.all(np.isfinite(n[k])) for n in a['wall_physics']['native_states_evaluation_only'] for k in ('qpos_evaluation_only','qvel_evaluation_only','command_torque_nm'))
        chronology=all(x['actual_activation_s']>=max(x['command_received_s'],x['command_ready_s'],x['requested_boundary_s'])-1e-10 for x in online if 'status' in x)
        passed=bool(mode['overall_result_for_mode']=='PASS' and certs and new_cert_nonvacuous and chronology)
        evidence=dict(run=str(path.relative_to(R)),physical_result='PASS' if passed else 'FAIL',physical_predicates=physical,unchanged_scorer_result=result,mode_aware_evaluation=mode,online_chronology_valid=chronology,finite_native=finite_native,new_activation_certificates_valid=certs,new_certificates_nonvacuous=new_cert_nonvacuous,scorer_source_sha256=hashlib.sha256((S/'scripts/high_rom_v1/summarize_phase_b.py').read_bytes()).hexdigest(),mode_evaluator_source_sha256=hashlib.sha256((S/'scripts/high_rom_v1/evaluate_execution_mode.py').read_bytes()).hexdigest(),scientific_host_age_scope='Unchanged existing mode-aware evaluator; raw scorer and 100ms wall-age result retained separately, without a realtime claim.')
        (path/'physical_audit.json').write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n');rows.append(evidence)
    (D/'CURRENT_VERSION_PHYSICAL_AUDIT.json').write_text(json.dumps(dict(rows=rows,scoring=scoring),indent=2,allow_nan=False)+'\n')
    print(json.dumps({'audited_runs':len(rows),'passes':sum(x['physical_result']=='PASS' for x in rows),'failed':[(x['run'],[k for k,v in x['physical_predicates'].items() if not v]) for x in rows if x['physical_result']!='PASS']}))
if __name__=='__main__':main()
