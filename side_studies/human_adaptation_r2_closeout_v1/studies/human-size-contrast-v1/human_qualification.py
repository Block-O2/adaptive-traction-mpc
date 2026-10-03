"""Bounded current-version qualification; wrappers only observe production calls."""
from pathlib import Path
import os,sys,json,hashlib,time,gzip,traceback,resource,csv
import numpy as np
W=Path('<SIDE_STUDIES_ROOT>/human-size-contrast-v1'); R=W/'snapshot'; S=R/'stages/stage5_personalized_motion_learning'
D=W; OUT=W/'runs'
for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning'):
    sys.path.insert(0,str(R/'stages'/stage/'src'))
from traction_mpc_stage5.full3d_adaptive_integration_v1 import runtime as rt
from traction_mpc_stage5.human_waypoint_shadow import HumanWaypointMPCShadowContractV1
from traction_mpc_stage5.architecture_recovery_v2.phase3_human_waypoint import AdaptiveHumanWaypointHWMPCV22,AdaptiveMechanicsScreenV22
from traction_mpc_stage4.estimator_v2 import DYNAMIC_BASE_PARAMETER_NAMES
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(rt._jsonable(x),indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
consumers={}
def consume(kind,model,sequence):
    row=consumers.setdefault(kind,{'calls':0,'versions':{},'first':None,'last':None})
    beta=model.beta.tolist(); key=hashlib.sha256(np.asarray(model.beta,dtype='<f8').tobytes()+np.asarray(model.residual_weights_nm,dtype='<f8').tobytes()).hexdigest()
    payload=dict(sequence=sequence,beta=beta,residual_weights_nm=model.residual_weights_nm.tolist(),numeric_model_sha256=key,geometry=rt._jsonable(dict(vars(model.geometry))))
    row['calls']+=1; row['versions'][str(sequence)]=key
    if row['first'] is None:row['first']=payload
    row['last']=payload
orig_command=HumanWaypointMPCShadowContractV1.command
def command(self,*a,**kw):
    obs=kw.get('observation'); consume('execution',self.human_model,None if obs is None else obs.human_model_version)
    return orig_command(self,*a,**kw)
HumanWaypointMPCShadowContractV1.command=command
orig_decide=AdaptiveHumanWaypointHWMPCV22.decide
def decide(self,*a,**kw):
    b=kw['belief']; consume('planner',b.human_model(),b.sequence)
    return orig_decide(self,*a,**kw)
AdaptiveHumanWaypointHWMPCV22.decide=decide
orig_screen=AdaptiveMechanicsScreenV22.evaluate
def screen(self,belief,candidate,schedule):
    consume('mechanics',belief.human_model(),belief.sequence)
    return orig_screen(self,belief,candidate,schedule)
AdaptiveMechanicsScreenV22.evaluate=screen
def main():
    contract=json.loads((D/'CONTRACT.json').read_text()); contract['cases']=[dict(id=e['case']['case_key'],path=e['path'],sha256=e['sha256'],case=e['case']) for e in contract['cases']]
    assert sha(R/contract['options_path'])==contract['options_sha256']
    options=json.loads((R/contract['options_path']).read_text())
    all_rows=[]
    selected=sys.argv[1:] or [c['id'] for c in contract['cases']]
    for c in contract['cases']:
        if c['id'] not in selected:continue
        assert sha(R/c['path'])==c['sha256']
        # All arms share exact truth and commissioning trajectory; execution options untouched.
        for arm in (os.environ['SIZE_STUDY_ARM'],):
            out=OUT/f"{c['id']}__{arm}"
            if (out/'qualification.json').exists() and json.loads((out/'qualification.json').read_text())['completion'] != 'EXCEPTION':continue
            if out.exists():out=OUT/f"{c['id']}__{arm}__attempt02"
            out.mkdir(parents=True,exist_ok=False); consumers.clear(); capture={'stop_check':resource_stop_check}; context={}
            start=time.monotonic(); print('START',c['id'],arm,flush=True)
            row=dict(condition=c['id'],arm=arm,evidence_category='current_version_development_qualification',case_path=c['path'],case_sha256=c['sha256'],human_truth=c['case']['physical'],task=c['case']['task'],parameter_names=list(DYNAMIC_BASE_PARAMETER_NAMES),command=sys.argv)
            try:
                summary=rt.run_executed_case(out,qualification_case=c['case'],qualification_arm=arm,
                    simulate_planning_latency=True,formal_qualification=False,dev_a_recovery=True,
                    dev_c_bumpless_transfer=False,dev_d_rigid_table_reference=True,
                    autonomous_recovery_options=options,task_timeout_s=30.,runtime_capture=capture,
                    execution_mode='SCIENTIFIC_SIMULATION',scientific_host_delay_s=0.,session_context=context)
                z=np.load(out/'trace.npz'); mask=z['stage']=='TASK'; t=z['time_s'][mask]; dt=np.diff(t)
                f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1); m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1)
                estimated=z['estimated_human_state_rad_rad_s'][mask]; truth=z['evaluation_only_human_state_rad_rad_s'][mask]
                qref=z['reference_q_rad'][mask]; rv=z['reference_dq_rad_s'][mask]
                u=context['updater']; adaptation=summary.get('adaptation_trace',capture.get('runtime',{}).get('adaptation_trace',[]))
                artifact=json.loads((out/'runtime_artifacts.json').read_text())
                adaptation=artifact.get('adaptation_trace',adaptation)
                beta=z['task_beta']; residual=z['task_residual_weights_nm']; versions=z['controller_model_version'][mask]
                pred=[x['diagnostics'].get('residual_sample_nm') for x in adaptation if x.get('diagnostics',{}).get('residual_sample_nm') is not None]
                row.update(completion=summary['status'],abort_reason=summary.get('abort_reason'),duration_s=float(t[-1]-t[0]) if len(t)>1 else 0.,
                    J_F_task_n_s=float(f[:-1]@dt),force_mean_n=float(np.mean(f)) if len(f) else None,force_rms_n=float(np.sqrt(np.mean(f*f))) if len(f) else None,force_peak_n=float(np.max(f)) if len(f) else None,
                    moment_integral_nm_s=float(m[:-1]@dt),moment_peak_nm=float(np.max(m)) if len(m) else None,
                    tracking_rmse_rad=np.sqrt(np.mean((estimated[:,:2]-qref)**2,axis=0)) if len(t) else None,
                    tracking_truth_rmse_rad_evaluation_only=np.sqrt(np.mean((truth[:,:2]-qref)**2,axis=0)) if len(t) else None,
                    minimum_clearance_m=summary['task'].get('minimum_session_clearance_m_deployable'),minimum_true_clearance_m_evaluation_only=summary['task'].get('minimum_true_physical_clearance_m_evaluation_only'),
                    initial_beta=summary['commissioning']['handoff_belief']['beta'],final_beta=u.dynamics.beta,
                    first_task_beta=beta[0] if len(beta) else None,final_task_beta=beta[-1] if len(beta) else None,
                    accepted_dynamic_updates_total=u.dynamics.accepted_updates,dynamic_identifier_record=u.dynamics.record(),
                    continual_update_attempts=summary['task']['continual_adaptation_update_count'],
                    residual_update_count=u.residual_update_count,residual_model_changed=bool(len(residual) and np.any(residual[-1]!=residual[0])),
                    prediction_residual_rms_nm=np.sqrt(np.mean(np.asarray(pred)**2,axis=0)) if pred else None,
                    geometry_estimate=summary['commissioning']['geometry_fit'],geometry_used=summary['commissioning']['handoff_belief']['effective_geometry'],
                    controller_model_versions=sorted(set(versions.tolist())),consumers=dict(consumers),no_nan_task=bool(all(np.all(np.isfinite(z[k][mask])) for k in ('estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','physical_cuff_force_world_n','physical_cuff_moment_world_nm','cr12_q_rad'))),
                    boundary_continuity=summary['timing']['all_reference_boundaries_q_dq_ddq_continuous'],
                    runtime_adaptation_trace_count=len(adaptation))
                # Keep representative and failure traces; other raw artifacts compressed, not rewritten history.
                for name in ('runtime_artifacts.json','summary.json','learning_transitions.jsonl'):
                    p=out/name
                    with gzip.open(str(p)+'.gz','wb',compresslevel=3) as dest:dest.write(p.read_bytes())
                    p.unlink()
            except Exception as e:
                row.update(completion='EXCEPTION',exception=f'{type(e).__name__}:{e}',traceback=traceback.format_exc(),consumers=dict(consumers))
                (out/'exception.txt').write_text(traceback.format_exc())
            row.update(elapsed_host_s=time.monotonic()-start,peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            save(out/'qualification.json',row); all_rows.append(row)
            print('DONE',c['id'],arm,row['completion'],row.get('abort_reason'),round(row['elapsed_host_s'],2),flush=True)
            state=json.loads((D/'STATE.json').read_text()); state.update(status='RUNNING',phase='HUMAN_QUALIFICATION',last_completed=f"{c['id']}__{arm}",next_action='Continue frozen three-arm case matrix');save(D/'STATE.json',state)
            capture.clear();context.clear();import gc;gc.collect()
    save(D/'INHERITED_HARNESS_AGGREGATE.json',{'status':'MEASUREMENTS_PENDING_CLASSIFICATION','runs':[json.loads(p.read_text()) for p in sorted(OUT.glob('*/qualification.json'))]})


# Separate study-only guard; never signals another process or touches shared STOP.
import subprocess
from datetime import datetime,timezone
_last_resource_check=0.; _swap_at_start=None
def windows_available_GiB():
    command="(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"
    result=subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command',command],text=True)
    return int(result.strip())/1048576.
def sample_resources():
    m={k:int(v.split()[0]) for line in Path('/proc/meminfo').read_text().splitlines() for k,v in [line.split(':',1)]}
    sac=Path('<PRIMARY_REPOSITORY>/stages/stage5_personalized_motion_learning/docs/single_human_sac_expert_v1/STATE.json')
    state=json.loads(sac.read_text())
    return dict(utc=datetime.now(timezone.utc).isoformat(),WSL_available_GiB=m['MemAvailable']/1048576.,Windows_available_GiB=windows_available_GiB(),swap_used_KiB=m['SwapTotal']-m['SwapFree'],SAC_phase=state.get('phase'),SAC_measurement=any(t in str(state.get('phase','')).upper() for t in ['THROUGHPUT','LATENCY','BENCHMARK']))
def resource_stop_check():
    global _last_resource_check
    if time.monotonic()-_last_resource_check<30.:return
    _last_resource_check=time.monotonic();r=sample_resources()
    with (W/'LIVE_RESOURCE_SAMPLES.jsonl').open('a') as stream:stream.write(json.dumps(r)+'\n')
    if (W/'SIDE_STOP').exists() or r['WSL_available_GiB']<2 or r['Windows_available_GiB']<4 or r['swap_used_KiB']>_swap_at_start or r['SAC_measurement']:
        raise RuntimeError('SIDE_STUDY_RESOURCE_PAUSE: save partial evidence; never signal SAC')
def validate_only():
    modules={k:str(v.__file__) for k,v in sys.modules.items() if k.startswith('traction_mpc') and getattr(v,'__file__',None)}
    assert all(p.startswith(str(R)) for p in modules.values())
    provenance=json.loads((W/'SOURCE_PROVENANCE.json').read_text())
    assert all(sha(R/p)==v['sha256'] for p,v in provenance['files'].items())
    assert sha(R/json.loads((W/'CONTRACT.json').read_text())['options_path'])==json.loads((W/'CONTRACT.json').read_text())['options_sha256']
    sys.path.insert(0,str(S/'scripts/high_rom_v1'))
    import evaluate_execution_mode,summarize_phase_b
    assert str(Path(evaluate_execution_mode.__file__).resolve()).startswith(str(R))
    save(W/'HARNESS_VALIDATION.json',dict(status='IMPORT_HASH_AND_GUARD_VALIDATED_DYNAMIC_UNTESTED',project_imports=modules,scorer_path=summarize_phase_b.__file__,mode_evaluator_path=evaluate_execution_mode.__file__,original_algorithm_unchanged=True,time_integration_steps=0,resource_release_present=(W/'RESOURCE_RELEASE.json').exists(),simulation_launched=False))
if __name__=='__main__':
    validate_only()
    if '--execute' not in sys.argv:
        print('CHECK_ONLY: no simulation. Execute requires current qualified aggregate-peak evidence and resource headroom.');sys.exit(0)
    sys.argv.remove('--execute')
    assert len(sys.argv)==2,'exactly one case per owner process'
    assert os.environ.get('SIZE_STUDY_ARM') in ('fixed_population','commissioning_only','continual_adaptive')
    entry=next(e for e in json.loads((W/'CONTRACT.json').read_text())['cases'] if e['case']['case_key']==sys.argv[1])
    audit=next(e for e in json.loads((W/'HUMAN_PARAMETER_AND_FEASIBILITY_AUDIT.json').read_text())['rows'] if e['height_m']==entry['height_m'])
    assert audit['structural_prior']['inside_prior'],'unsupported anatomy prior: no execution in v1'
    release=json.loads((W/'RESOURCE_RELEASE.json').read_text())
    assert release['aggregate_parent_and_planner_peak_verified'] is True
    assert release['runtime_sha256']==sha(S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime.py')
    assert release['peak_evidence_paths'] and all(Path(p).is_file() for p in release['peak_evidence_paths'])
    peak=float(release['conservative_peak_GiB']);assert peak>0
    r=sample_resources();assert not r['SAC_measurement']
    assert r['WSL_available_GiB']>=peak+2 and r['Windows_available_GiB']>=peak+4
    assert r['swap_used_KiB']==0
    _swap_at_start=r['swap_used_KiB']
    state=json.loads((W/'STATE.json').read_text())
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(state['started_utc'])).total_seconds()
    assert elapsed<=6*3600,'v1 total time cap; do not automatically restart'
    assert not (OUT/(sys.argv[1]+'__'+os.environ['SIZE_STUDY_ARM'])).exists(),'deterministic retry requires explicit diagnostic slot'
    assert state['primary_runs_executed']<9
    state['primary_runs_executed']+=1;save(W/'STATE.json',state)
    save(W/'LAST_LAUNCH.json',dict(resources=r,arm=os.environ['SIZE_STUDY_ARM'],case=sys.argv[1],started_utc=datetime.now(timezone.utc).isoformat()))
    main()
