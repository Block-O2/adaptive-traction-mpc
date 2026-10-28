"""Read an already completed B's causal history, with original trace closure.

No file writes, fits, rollouts, or evaluation-only Human/native-array reads.
This reader is for explicit COLD_REPLAY history-conditioned selection unless
the orchestrator separately proves real persistent-session continuity.
"""
from pathlib import Path
import hashlib
import json
import math
import numpy as np
from trial_interface import summarize,feature_vector


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())


def load_completed_b_history(package_root, group, *, config=None, patient_id=None,
                             trial_number=1, expected_case_sha256=None):
    """Return {history, feature_names, features, integrity, sources}.

    `config` is the actual frozen worker config containing case_path, or the
    function reads experiments/<group>.json / runtime/<group>_TEST_PLAN.json.
    All data must already have been persisted by the completed B invocation.
    No missing field is filled with zero and no terminal sample is invented.
    """
    root=Path(package_root);ident=group+'_B'
    if config is None:
        candidates=[root/'experiments'/f'{group}.json',root/'runtime'/f'{group}_TEST_PLAN.json']
        config_path=next((p for p in candidates if p.is_file()),None)
        if config_path is None:raise FileNotFoundError('FROZEN_CONFIG_REQUIRED')
        config=read(config_path)
    paths=dict(history=root/'history'/f'{ident}_CAUSAL_HISTORY.json',
        trace=root/'runtime/source/results'/ident/'trace.npz',
        summary=root/'runtime/source/results'/ident/'summary.json',
        measured=root/'runtime/reports'/f'{ident}_MEASURED.json')
    case_path=Path(config['case_path'])
    if not case_path.is_absolute():case_path=root/case_path
    case=read(case_path);case_sha=sha(case_path)
    if expected_case_sha256 is not None and case_sha!=expected_case_sha256:
        raise ValueError('CASE_IDENTITY_MISMATCH')
    if config.get('case_sha256') and case_sha!=config['case_sha256']:
        raise ValueError('CONFIG_CASE_IDENTITY_MISMATCH')
    history=read(paths['history']);summary=read(paths['summary']);measured=read(paths['measured'])
    if summary['status']!='COMPLETE':raise ValueError('B_NOT_COMPLETE')
    result_path=root/'attempts'/f'{ident}_RESULT.json'
    if result_path.is_file() and read(result_path).get('qualified') is not True:
        raise ValueError('ORIGINAL_B_NOT_QUALIFIED')
    binding_path=root/'attempts'/f'{ident}_EXECUTION_BINDING.json'
    if binding_path.is_file() and read(binding_path)['action'].get('family')!='B':
        raise ValueError('HISTORY_NOT_FROM_ACTUAL_B_ACTION')
    permitted=['stage','time_s','task_phase','terminal_boundary_node',
        'estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s',
        'physical_cuff_force_world_n','physical_cuff_moment_world_nm']
    with np.load(paths['trace'],allow_pickle=False) as archive:
        z={key:archive[key] for key in permitted}
    ids=np.flatnonzero(z['stage']=='TASK')
    if len(ids)!=len(history)+1 or not bool(z['terminal_boundary_node'][ids[-1]]):
        raise ValueError('EXPECTED_EXACTLY_ONE_MISSING_TERMINAL_BOUNDARY')
    arrays=dict(time_s=z['time_s'][ids[:-1]],estimated_q_dq=z['estimated_human_state_rad_rad_s'][ids[:-1]],
        reference_q_dq=np.c_[z['reference_q_rad'][ids[:-1]],z['reference_dq_rad_s'][ids[:-1]]],
        measured_force=z['physical_cuff_force_world_n'][ids[:-1]],
        measured_moment=z['physical_cuff_moment_world_nm'][ids[:-1]])
    errors={key:float(np.max(np.abs(np.asarray([r[key] for r in history],float)-a))) for key,a in arrays.items()}
    if any(value!=0. for value in errors.values()):raise ValueError('HISTORY_TRACE_NOT_EXACTLY_MATCHED')
    if [r['phase'] for r in history]!=z['task_phase'][ids[:-1]].tolist():
        raise ValueError('HISTORY_TRACE_PHASE_MISMATCH')
    completion=[r for r in summary['task']['phase_transitions'] if r['to']=='COMPLETE']
    if len(completion)!=1:raise ValueError('EXACT_CAUSAL_COMPLETE_COMMIT_REQUIRED')
    completion=completion[0];last=int(ids[-1]);end=float(z['time_s'][last])
    if abs(float(completion['time_s'])-end)>1e-12 or not np.array_equal(
            np.asarray(completion['estimated_state']),z['estimated_human_state_rad_rad_s'][last]):
        raise ValueError('TERMINAL_CAUSAL_COMPLETE_COMMIT_MISMATCH')
    terminal=dict(time_s=end,phase=str(z['task_phase'][last]),
        estimated_q_dq=z['estimated_human_state_rad_rad_s'][last].tolist(),
        reference_q_dq=np.r_[z['reference_q_rad'][last],z['reference_dq_rad_s'][last]].tolist(),
        measured_force=z['physical_cuff_force_world_n'][last].tolist(),
        measured_moment=z['physical_cuff_moment_world_nm'][last].tolist(),
        source_sample_time_s=float(completion['state_source_time_s']),truth_used=False)
    rows=history+[terminal];start=history[0]['reference_q_dq'][:2]
    goal=[math.radians(v) for v in case['task']['goal_deg']]
    identity=dict(case_sha256=case_sha,trace_sha256=sha(paths['trace']),source_history_sha256=sha(paths['history']),
        group=group,source='completed_real_B_cold_replay_history_not_persistent_proof')
    h=summarize(rows,trial_id=ident,patient_id=patient_id or group,trial_number=trial_number,
        actual_action_tag='B',task_start_s=rows[0]['time_s'],task_end_s=end,complete=True,
        identity=identity,public_phase_targets={'OUTBOUND':[start,goal],'RETURN':[goal,start]})
    jf_error=h['JF_N_s']-measured['J_F_N_s'];jm_error=h['JM_Nm_s']-measured['moment_integral_Nm_s']
    if abs(jf_error)>1e-6 or abs(jm_error)>1e-6:raise ValueError('ORIGINAL_JF_JM_CLOSURE_FAILED')
    names,features=feature_vector(h)
    files=list(paths.values())+[case_path]
    return dict(history=h,feature_names=names,features=features,
        integrity=dict(exact_preterminal_field_errors=errors,original_missing_terminal_boundary=True,
            restored_terminal_from_existing_trace_and_causal_complete_commit=True,
            trace_allowlist=permitted,JF_closure_error_N_s=jf_error,JM_closure_error_Nm_s=jm_error,
            native_truth_arrays_read=False,missing_fields_filled_with_zero=False,
            persistent_physical_continuity_inferred=False),
        sources=[dict(path=str(p),sha256=sha(p)) for p in files])
