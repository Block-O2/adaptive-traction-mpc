"""Stored optional telemetry availability, never imputed/reconstructed."""
from pathlib import Path
import importlib.util,json,hashlib,sys,collections
import numpy as np
sys.dont_write_bytecode=True
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
spec=importlib.util.spec_from_file_location('raw_telemetry_offline',P/'control/independent_recompute.py')
raw=importlib.util.module_from_spec(spec);spec.loader.exec_module(raw)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def finite_stats(x):
    finite=np.isfinite(x);rows=np.all(finite,axis=1)
    return dict(total_rows=len(x),finite_elements=int(finite.sum()),total_elements=x.size,
        fully_finite_rows=int(rows.sum()),any_nonfinite_rows=int((~rows).sum()),
        availability='ALL_FINITE' if finite.all() else 'ALL_NONFINITE_OPTIONAL' if not finite.any() else 'PARTIAL_FINITE_TELEMETRY',
        finite_rows_only_peak_abs=np.max(abs(x[rows]),axis=0).tolist() if rows.any() else None,
        finite_rows_only_rms=np.sqrt(np.mean(x[rows]*x[rows],axis=0)).tolist() if rows.any() else None,
        finite_rows_only_statistics_are_availability_diagnostics_not_full_task_metrics=True)
def run(ident):
    out=P/'audit'/(ident+'_OPTIONAL_TELEMETRY_AVAILABILITY.json')
    if out.exists():return read(out)
    patient=ident.split('_')[0]
    assert read(P/'audit'/(patient+'_OWNER.json'))['joined']
    assert read(P/(patient+'_WORKER_EXIT.json'))['active_child'] is None
    folder=P/'source/results'/ident;src=[folder/'trace.npz',folder/'runtime_artifacts.json.gz']
    before={str(p):sha(p) for p in src};fields={}
    with np.load(src[0]) as z:
        for k in z.files:
            if k in ['cr12_actuator_command_nm','allocated_wrench_world','applied_generalized_action_nm'] or k.startswith('robot_torque_component_'):
                x=z[k];task=z['stage']=='TASK';m=finite_stats(x[task]);bad=task & ~np.all(np.isfinite(x),axis=1)
                m.update(all_stage=finite_stats(x),missing_task_physical_times_s=z['time_s'][bad].tolist(),
                    missing_task_boundary_flags=z['terminal_boundary_node'][bad].tolist() if 'terminal_boundary_node' in z.files else None)
                fields[k]=m
    arrays={}
    target_keys=['robot_torque_components','allocated_wrench_world','applied_robot_tau_nm','command_torque_nm','selected_command_force_total_n','selected_command_moment_total_nm','generalized_action_nm']
    for array in ['trace','execution_attempts','command_receipts']:
        n=0;present=collections.Counter();finite=collections.Counter();allkeys=set()
        try:
            for row in raw.array_items(src[1],array):
                n+=1;allkeys.update(row)
                for key in target_keys:
                    if key in row:
                        present[key]+=1
                        value=row[key]
                        if isinstance(value,dict):okay=all(np.all(np.isfinite(np.asarray(v,float))) for v in value.values())
                        else:okay=np.all(np.isfinite(np.asarray(value,float)))
                        if okay:finite[key]+=1
            arrays[array]=dict(rows=n,present_counts=dict(present),finite_counts=dict(finite),
                               matching_all_keys=sorted(k for k in allkeys if any(x in k for x in ['torque','wrench','allocat','generalized'])))
        except ValueError as e:arrays[array]=dict(error=str(e),rows=n)
    data=dict(id=ident,summary_status=read(folder/'summary.json')['status'],trace_fields=fields,runtime_array_fields=arrays,
        source_hashes=before,original_bytes_unchanged=all(sha(p)==h for p,h in before.items()),
        interpretation='Column presence does not establish finite telemetry. Original max/RMS uses ordinary reductions so even one NaN can propagate to JSON null; finite-only diagnostics are explicitly separate. Actual actuator torque and stored selected command force/moment are not relabeled as a full allocator decomposition.',
        missing_values_imputed=False,unknown_outputs_reconstructed=False,new_physics_starts=0)
    assert data['original_bytes_unchanged']
    for root in [P,Path(read(P/'ENVIRONMENT.json')['review'])]:
        dest=root/'audit'/out.name;assert not dest.exists();dest.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(id=ident,trace={k:dict(availability=v['availability'],finite=v['fully_finite_rows'],total=v['total_rows']) for k,v in fields.items()},runtime=arrays)),flush=True)
    return data
if __name__=='__main__':
    ids=sys.argv[1:]
    if not ids:
        ids=[]
        for patient in read(P/'VIRTUAL_PATIENT_COHORT.json')['order']:
            if (P/'audit'/(patient+'_OWNER.json')).exists() and read(P/'audit'/(patient+'_OWNER.json'))['joined']:
                ids.extend(patient+'_'+arm for arm in ['B','H150','parent'] if (P/'source/results'/(patient+'_'+arm)/'trace.npz').exists())
    rows=[run(ident) for ident in ids]
    print('TELEMETRY_AUDITED',len(rows),flush=True)
