"""Final offline 36-run telemetry coverage and receipt-bound interval statistics."""
from pathlib import Path
import importlib.util,json,hashlib,sys
import numpy as np
sys.dont_write_bytecode=True
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
spec=importlib.util.spec_from_file_location('raw_interval_telemetry',P/'control/independent_recompute.py')
raw=importlib.util.module_from_spec(spec);spec.loader.exec_module(raw)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
optional=['robot_torque_component_'+k+'_nm' for k in ['base','position','velocity','allocator','clipping']]+['allocated_wrench_world']
assert read(P/'SERIAL_CAMPAIGN_DONE.json')['owned_children_joined']
rows=[]
for patient in read(P/'VIRTUAL_PATIENT_COHORT.json')['order']:
    assert read(P/'audit'/(patient+'_OWNER.json'))['joined']
    assert read(P/(patient+'_WORKER_EXIT.json'))['active_child'] is None
    for arm in ['B','H150','parent']:
        ident=patient+'_'+arm;folder=P/'source/results'/ident
        files=[folder/'trace.npz',folder/'runtime_artifacts.json.gz',folder/'summary.json']
        hashes={str(p):sha(p) for p in files}
        receipts=list(raw.array_items(files[1],'command_receipts'))
        positive=sorted([r for r in receipts if r.get('applied') is True and r.get('native_steps',0)>0],key=lambda r:r['start_physics_s'])
        starts=np.array([r['start_physics_s'] for r in positive]);fields={}
        receipt_payload={}
        for name in ['command_torque_nm','selected_command_force_total_n','selected_command_moment_total_nm']:
            present=[r[name] for r in receipts if name in r]
            receipt_payload[name]=dict(receipts=len(receipts),present=len(present),finite=sum(bool(np.all(np.isfinite(x))) for x in present))
        with np.load(files[0]) as z:
            global_indices=np.where(z['stage']=='TASK')[0];t=z['time_s'][global_indices];dt=np.r_[np.diff(t),0.];use=dt>1e-12
            assert np.all(dt>=-1e-12)
            boundary=z['terminal_boundary_node'][global_indices]
            actual=z['cr12_actuator_command_nm'][global_indices]
            receipt_join=[]
            for i in np.where(use)[0]:
                j=int(np.searchsorted(starts,t[i]+1e-8,side='right')-1);assert j>=0
                r=positive[j]
                assert abs(r['start_physics_s']-t[i])<1e-8 and abs(r['end_physics_s']-t[i+1])<1e-8,'TRACE_INTERVAL_NOT_EXACT_RECEIPT'
                assert np.array_equal(actual[i],np.array(r['command_torque_nm'])),'TRACE_ACTUATOR_RECEIPT_MISMATCH'
                receipt_join.append(r['receipt_index'])
            for key in ['cr12_actuator_command_nm','applied_generalized_action_nm']+optional:
                x=z[key][global_indices];finite=np.all(np.isfinite(x),axis=1);bad=np.where(~finite)[0];interior=bad[use[bad]]
                valid=bool(np.all(finite[use]));terminal_only=bool(len(bad)>0 and np.all(bad==len(t)-1) and np.all(boundary[bad]) and np.all(dt[bad]==0))
                fields[key]=dict(task_rows=len(t),fully_finite_rows=int(finite.sum()),nonfinite_rows=len(bad),
                    nonfinite_task_row_indices=bad.tolist(),nonfinite_full_trace_indices=global_indices[bad].tolist(),
                    nonfinite_physical_times_s=t[bad].tolist(),nonfinite_terminal_boundary_flags=boundary[bad].tolist(),
                    nonfinite_rows_with_following_positive_interval=interior.tolist(),
                    missing_only_terminal_no_following_interval=terminal_only,
                    positive_interval_coverage_complete=valid,positive_intervals=int(use.sum()),covered_duration_s=float(dt[use].sum()),
                    applied_interval_peak_abs=np.max(abs(x[use]),axis=0).tolist() if valid else None,
                    applied_interval_time_weighted_rms=np.sqrt(np.sum(x[use]**2*dt[use,None],axis=0)/dt[use].sum()).tolist() if valid else None,
                    original_null_statistics_unchanged=True,missing_values_filled=False)
            components=sum(z[k][global_indices][use] for k in optional[:-1])
            component_error=float(np.max(abs(components-actual[use])))
            reference_error=[]
            for i,rid in zip(np.where(use)[0],receipt_join):
                r=next_receipt=None
                # Receipt indices are unique, but not used as an assumed list offset.
                r=positive[int(np.searchsorted(starts,t[i]+1e-8,side='right')-1)]
                selected=np.r_[r['selected_command_force_total_n'],r['selected_command_moment_total_nm']]
                reference_error.append(float(np.max(abs(z['allocated_wrench_world'][global_indices[i]]-selected))))
        row=dict(id=ident,summary_status=read(files[2])['status'],scope='COMPLETE_TASK_APPLIED_INTERVALS' if read(files[2])['status']=='COMPLETE' else 'OBSERVED_PREFIX_APPLIED_INTERVALS',
            source_hashes=hashes,source_bytes_unchanged=all(sha(p)==h for p,h in hashes.items()),fields=fields,
            positive_task_intervals_exactly_joined_to_applied_receipts=len(receipt_join),trace_actuator_matches_receipt_exactly=True,
            decomposition_sum_vs_actual_max_abs_nm=component_error,decomposition_sum_matches_actual=component_error<1e-8,
            allocated_wrench_vs_receipt_selected_command_max_abs=max(reference_error),
            receipt_payload_availability=receipt_payload)
        assert row['source_bytes_unchanged'];rows.append(row)
        print('INTERVAL_TELEMETRY',ident,row['scope'],len(receipt_join),flush=True)
result=dict(status='PASS' if all(r['source_bytes_unchanged'] and r['trace_actuator_matches_receipt_exactly'] and all(f['positive_interval_coverage_complete'] for f in r['fields'].values()) for r in rows) else 'INCOMPLETE_TELEMETRY',
    runs=len(rows),rows=rows,weighting='Each TASK trace left-node value applies over [time_s[i],time_s[i+1]). Include every positive-duration interval, joined to the exact applied receipt and torque. max=max(abs(x_i)); RMS=sqrt(sum(x_i**2*dt_i)/sum(dt_i)) per component. Last no-following-interval boundary has zero weight. Any nonfinite positive-duration interval makes both new reductions null; interior missing data are never silently dropped.',
    all_optional_missing_task_rows_are_terminal_only=all(r['fields'][k]['missing_only_terminal_no_following_interval'] for r in rows for k in optional),
    task_versus_whole_session='These reductions cover TASK or observed TASK prefix only. Optional component telemetry is also absent on some commissioning/session rows; no whole-session completeness claim.',
    original_frozen_reductions='Preserved byte-for-byte. Original ordinary np.max/mean propagate final-boundary NaN and clean() writes JSON null. Additive interval reductions do not replace those values.',
    unavailable_boundary_values_reconstructed=False,new_physics_starts=0,controller_modified=False)
assert not any(k in sys.modules for k in ['mujoco','study_common','cross_runner','sac_env'])
for root in [P,Path(read(P/'ENVIRONMENT.json')['review'])]:
    dest=root/'audit/TELEMETRY_AVAILABILITY_REDUCTION_AUDIT.json';assert not dest.exists();dest.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps(dict(status=result['status'],runs=len(rows),all_optional_missing_task_rows_are_terminal_only=result['all_optional_missing_task_rows_are_terminal_only'])),flush=True)
