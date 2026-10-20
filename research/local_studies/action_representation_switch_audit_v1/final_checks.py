"""Final archive/provenance checks only; no experiment execution."""
from common import *
import ast
for p in P.glob('*.py'):ast.parse(p.read_text())
for seed in read('PLAN_FROZEN.json')['seeds']:
    c=read(f'CLOSED_LOOP_seed_{seed}.json');assert c['teacher_reads_during_rollout']==c['teacher_overrides']==0
    assert c['category']=='DIAGNOSTIC_NOT_OLD_GATE'
    data=np.load(O/f'POLICY_seed_{seed}.npz')
    assert data['observations'].shape==(c['steps'],55)
    assert data['raw_actions'].shape==data['executed_actions'].shape==(c['steps'],2)
    assert np.isfinite(data['observations']).all()
    assert Path(c['episode_dir']).joinpath('runtime_artifacts.json.gz').is_file()
lock();pres=read('PRESERVATION_FINAL.json');assert not pres['changed'] and pres['index_unchanged'] and pres['HEAD_unchanged']
report=O/'ACTION_REPRESENTATION_SWITCH_AUDIT_V1_REPORT.md'
text=report.read_text().replace('REPRESEN­TATION_SMOOTHNESS.json (filename REPRESENTATION_SMOOTHNESS.json)','REPRESENTATION_SMOOTHNESS.json')
text=text.replace('- Executed: preflight.py,', '- Finalization timing repair: the resume script reached finish.py before that file had been saved. The missing-file log remains; finish.py was then executed separately after completion of all three existing-checkpoint runs and all three fixed-budget delta fits. No physics or fit was repeated for this repair.\n- Executed: preflight.py,')
report.write_text(text,encoding='utf-8')
save('FINAL_CHECKS.json',dict(status='PASS',script_syntax=True,complete_policy_arrays_all_three=True,teacher_rollout_reads=0,teacher_overrides=0,SAC_steps=0,physics_runs=3,offline_fits=3,figures_visually_inspected=['SWITCH_ZOOM.png','CLOSED_LOOP_seed_20261006.png'],visual_QA='readable axes/legends, complete requested teacher switch channels and diagnostic raw/executed/reference/actual/force/moment/clearance channels; labels distinguish teacher-state predictions from autonomous replay',historical_integrity=pres['changed']==[],report_path=report))
save('AUDIT_SOURCE_MANIFEST.json',{p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in P.iterdir() if p.is_file()})
save('EVIDENCE_MANIFEST.json',{str(p.relative_to(O)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in O.rglob('*') if p.is_file() and p.name!='EVIDENCE_MANIFEST.json'})
print(json.dumps(dict(status='FINAL_CHECKS_PASS_STOP',historical_native_files=pres['protected_native_files'],historical_windows_files=pres['protected_windows_files'],report=str(report))),flush=True)
