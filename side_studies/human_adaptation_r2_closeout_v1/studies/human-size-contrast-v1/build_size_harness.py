from pathlib import Path
import json,hashlib,ast,shutil
W=Path('<SIDE_STUDIES_ROOT>/human-size-contrast-v1');S=W/'snapshot/stages/stage5_personalized_motion_learning'
original=(W/'human_qualification_inherited.py').read_text();text=original
text=text.replace("R=Path('<PRIMARY_REPOSITORY>'); S=R/'stages/stage5_personalized_motion_learning'", "W=Path('<SIDE_STUDIES_ROOT>/human-size-contrast-v1'); R=W/'snapshot'; S=R/'stages/stage5_personalized_motion_learning'")
text=text.replace("D=S/'docs/adaptive_human_online_interface_v1'; OUT=S/'results/adaptive_human_online_interface_v1/human'", "D=W; OUT=W/'runs'")
text=text.replace("contract=json.loads((D/'EXPERIMENT_CONTRACT.json').read_text())", "contract=json.loads((D/'CONTRACT.json').read_text()); contract['cases']=[dict(id=e['case']['case_key'],path=e['path'],sha256=e['sha256'],case=e['case']) for e in contract['cases']]")
text=text.replace("for arm in ('continual_adaptive','commissioning_only','fixed_population'):", "for arm in (os.environ['SIZE_STUDY_ARM'],):")
text=text.replace("capture={}; context={}", "capture={'stop_check':resource_stop_check}; context={}")
text=text.replace("state.update(phase='HUMAN_QUALIFICATION'", "state.update(status='RUNNING',phase='HUMAN_QUALIFICATION'")
text=text.replace("'CURRENT_HUMAN_ADAPTATION_VALIDATION.json'", "'INHERITED_HARNESS_AGGREGATE.json'")
text=text.replace("if __name__=='__main__':main()", "")
# Preserve exact inherited hooks and metrics; add geometry signatures explicitly.
text=text.replace("payload=dict(sequence=sequence,beta=beta,residual_weights_nm=model.residual_weights_nm.tolist(),numeric_model_sha256=key)", "payload=dict(sequence=sequence,beta=beta,residual_weights_nm=model.residual_weights_nm.tolist(),numeric_model_sha256=key,geometry=rt._jsonable(dict(vars(model.geometry))))")
footer='''
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
    with (W/'LIVE_RESOURCE_SAMPLES.jsonl').open('a') as stream:stream.write(json.dumps(r)+'\\n')
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
'''
text+=footer
ast.parse(text);(W/'human_qualification.py').write_text(text)
# Reference source is evidence, not an executable runner with main-project paths.
(W/'human_qualification_inherited.py').rename(W/'human_qualification_inherited.py.txt')
shutil.copy2(__file__,W/'build_size_harness.py')
print(json.dumps({'runner':str(W/'human_qualification.py'),'sha256':hashlib.sha256(text.encode()).hexdigest(),'simulation_launched':False}))
