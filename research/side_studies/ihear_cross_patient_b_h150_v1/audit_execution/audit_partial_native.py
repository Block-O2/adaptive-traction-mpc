"""Independent raw ownership of a joined incomplete physical run.

Verifies retained native/receipt intervals and observed-prefix arithmetic only.
No full-task metric, gain, task pass, or safety pass is inferred from this audit.
"""
from pathlib import Path
import importlib.util,json,hashlib,collections,sys
import numpy as np
sys.dont_write_bytecode=True
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
spec=importlib.util.spec_from_file_location('raw_partial_offline',P/'control/independent_recompute.py')
raw=importlib.util.module_from_spec(spec);spec.loader.exec_module(raw)
def read(p,default=None):return json.loads(Path(p).read_text()) if Path(p).exists() else default
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def run(ident):
    patient=ident.split('_')[0]
    assert read(P/'audit'/(patient+'_OWNER.json'),{}).get('joined'),'WAIT_FOR_JOIN'
    assert read(P/(patient+'_DONE.json'))['all_children_joined']
    assert read(P/(patient+'_WORKER_EXIT.json'))['active_child'] is None
    folder=P/'source/results'/ident;artifact=folder/'runtime_artifacts.json.gz'
    ev=read(P/'reports'/(ident+'_CROSS_EVALUATION.json'));su=read(folder/'summary.json')
    assert ev['complete_task'] is False and ev['J_F_N_s'] is None
    source_paths=[artifact,folder/'trace.npz',folder/'summary.json',P/'reports'/(ident+'_CROSS_EVALUATION.json')]
    before={str(f):sha(f) for f in source_paths}
    receipts=list(raw.array_items(artifact,'command_receipts'))
    positive=sorted([r for r in receipts if r.get('applied') is True and r.get('native_steps',0)>0],key=lambda r:r['start_physics_s'])
    assert positive,'NO_POSITIVE_RECEIPTS'
    assert all(abs(a['end_physics_s']-b['start_physics_s'])<1e-8 for a,b in zip(positive,positive[1:])),'RECEIPT_GAP_OR_OVERLAP'
    assert len({r['receipt_index'] for r in receipts})==len(receipts),'DUPLICATE_RECEIPT_ID'
    count=collections.Counter();index=0;n=0;previous_t=None;first_t=None;task_native=0;direct_ids=0;by_mode=collections.Counter();phases=collections.Counter()
    with np.load(folder/'trace.npz') as z:
        task=z['stage']=='TASK';t=z['time_s'][task];force=np.linalg.norm(z['physical_cuff_force_world_n'][task],axis=1)
        assert len(t)>=2 and np.all(np.diff(t)>=-1e-12)
        prefix=float(force[:-1]@np.diff(t));duration=float(t[-1]-t[0])
    for row in raw.array_items(artifact,'native_states_evaluation_only'):
        rt=row['time_s'];begin=row.get('physical_interval_start_s',rt-.00025)
        if first_t is None:first_t=rt
        if previous_t is not None:assert abs(rt-previous_t-.00025)<1e-9,'NATIVE_GRID_GAP'
        previous_t=rt
        while index+1<len(positive) and begin>=positive[index]['end_physics_s']-1e-9:index+=1
        receipt=positive[index]
        assert receipt['start_physics_s']-1e-8<=begin<receipt['end_physics_s']+1e-8,'NATIVE_OUTSIDE_RECEIPT'
        assert row['command_torque_nm']==receipt['command_torque_nm'],'TORQUE_MISMATCH'
        if row.get('command_id') is not None:
            direct_ids+=1;assert row['command_id']==receipt['receipt_index'],'COMMAND_ID_MISMATCH'
        count[receipt['receipt_index']]+=1;n+=1;by_mode[receipt.get('mode')]+=1
        if t[0]-1e-9<=begin<t[-1]-1e-9:task_native+=1
    assert all(count[r['receipt_index']]==r['native_steps'] for r in positive),'NATIVE_COUNT_MISMATCH'
    assert n==sum(r['native_steps'] for r in positive)
    assert abs(task_native*.00025-duration)<1e-7,'PREFIX_NATIVE_DURATION_MISMATCH'
    ages=[r['sensor_age_at_apply_ms'] for r in receipts if r.get('applied') and r.get('apply_ns') is not None and r.get('sensor_age_at_apply_ms') is not None]
    assert all(0<=a<=100+1e-7 for a in ages),'COMMAND_SOURCE_AGE_FAIL'
    intervention_rows=[]
    kinds={'terminal_duration_intervention':'T','second_round_posture':'D','early_return_duration':'ER','terminal_hip_timing':'H150'}
    for record in su.get('learning_records',[]):
        screen=record.get('selected_plan',{}).get('execution_screen',{})
        present=[(name,kinds[name]) for name in kinds if name in screen]
        if not present:continue
        lo=record.get('start_time_s');hi=record.get('end_time_s')
        time_domain_valid=bool(lo is not None and hi is not None and t[0]-1e-8<=lo<=hi<=t[-1]+1e-8)
        owned_steps=None
        if time_domain_valid:
            owned_steps=sum(round(max(0,min(r['end_physics_s'],hi)-max(r['start_physics_s'],lo))/.00025) for r in positive)
        for name,kind in present:intervention_rows.append(dict(kind=kind,decision_index=record.get('decision_index'),metadata=screen[name],activated=record.get('selected_plan_activated'),start_time_s=lo,end_time_s=hi,time_domain_valid=time_domain_valid,receipt_owned_steps_in_record_interval=owned_steps,
            attribution='Positive command interval coverage during this activated record; exact schedule counterfactual attribution is not inferred.'))
    request_rows=list(raw.array_items(artifact,'requests'))
    scientific=ev['axes']['original_evaluator'].get('scientific_validity')
    outcome=collections.Counter(r.get('outcome') for r in request_rows)
    reasons=[dict(request_id=r.get('request_id'),stage=r.get('stage'),outcome=r.get('outcome'),reason=r.get('reason'),source_sample_time_s=r.get('source_sample_time_s')) for r in request_rows if r.get('outcome')!='ACTIVATED']
    data=read(P/'output'/(ident+'_DATA.json'),{})
    result=dict(id=ident,status='PARTIAL_RAW_OWNERSHIP_PASS',summary_status=su['status'],abort_reason=su.get('abort_reason'),
         complete_task=False,full_J_F_N_s=None,full_gain=None,scientific_promotion=False,
         observed_prefix_J_F_N_s=prefix,observed_prefix_duration_s=duration,task_trace_rows=len(t),
         native_rows=n,first_native_time_s=first_t,last_native_time_s=previous_t,task_native_intervals=task_native,
         retained_native_rows_include_shared_prefix=True,actual_new_native_physics_steps=data.get('metric',{}).get('actual_new_native_physics_steps'),
         receipt_count=len(receipts),positive_applied_receipts=len(positive),every_native_row_owned=True,
         exact_torque_checked=True,direct_command_id_checked_rows=direct_ids,each_receipt_step_count_matches=True,
         maximum_applied_source_age_ms=max(ages,default=None),native_steps_by_applied_mode=dict(by_mode),
         request_outcomes=dict(outcome),nonactivated_requests=reasons,original_scientific_validity=scientific,
         intervention_rows=intervention_rows,source_hashes=before,original_bytes_unchanged=all(sha(f)==h for f,h in before.items()),
         interpretation='Task/causal qualification failure is preserved. Retained native command ownership can pass despite a rejected request and incomplete task. Absolute safety status covers observed prefix only.',new_physics_starts=0)
    assert result['original_bytes_unchanged']
    for root in [P,Path(read(P/'ENVIRONMENT.json')['review'])]:
        dest=root/'audit'/(ident+'_PARTIAL_NATIVE_OWNERSHIP.json');assert not dest.exists()
        dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(id=ident,status=result['status'],native_rows=n,task_native_intervals=task_native,prefix_J=prefix,duration=duration,request_outcomes=dict(outcome),scientific_reasons=scientific.get('reasons') if scientific else None)))
if __name__=='__main__':
    for ident in sys.argv[1:]:run(ident)
