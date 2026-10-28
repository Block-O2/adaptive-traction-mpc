"""Authorized <=60s no-fit extraction of six exposed OUT0 complete-B histories."""
from pathlib import Path
import hashlib
import json
import math
import os
import resource
import signal
import time

os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
import numpy as np
import trial_interface as ti

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OLD=ROOT/'autonomous_learning_smoothness_v7'
GROUPS=['EARLYN01','EARLYH01','EARLYL01','CFACTORH01','CFACTORL01','HOLDSS03']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())


def main():
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('REGISTERED_EXTRACTION_60S')))
    signal.alarm(60);started=time.time();cpu=time.process_time();results=[];sources=[]
    for group in GROUPS:
        history_path=OLD/'history'/f'{group}_B_CAUSAL_HISTORY.json'
        trace_path=OLD/'runtime/source/results'/f'{group}_B'/'trace.npz'
        summary_path=OLD/'runtime/source/results'/f'{group}_B'/'summary.json'
        measured_path=OLD/'runtime/reports'/f'{group}_B_MEASURED.json'
        plan_path=OLD/'runtime'/f'{group}_TEST_PLAN.json'
        history=read(history_path);summary=read(summary_path);measured=read(measured_path);plan=read(plan_path)
        if summary['status']!='COMPLETE':raise ValueError('NONCOMPLETE_B:'+group)
        case_path=OLD/plan['case_path'];case=read(case_path)
        with np.load(trace_path,allow_pickle=False) as archive:
            # Explicit archive-key allowlist. Evaluation-only Human state,
            # accelerations, true clearance and native arrays are never loaded.
            permitted=['stage','time_s','task_phase','terminal_boundary_node',
                'estimated_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s',
                'physical_cuff_force_world_n','physical_cuff_moment_world_nm']
            z={key:archive[key] for key in permitted}
        ids=np.flatnonzero(z['stage']=='TASK')
        if len(ids)!=len(history)+1 or not bool(z['terminal_boundary_node'][ids[-1]]):
            raise ValueError('UNEXPECTED_TRACE_BOUNDARY_SHAPE:'+group)
        pairs=[('time_s','time_s'),('estimated_q_dq','estimated_human_state_rad_rad_s'),
               ('reference_q_dq',None),('measured_force','physical_cuff_force_world_n'),
               ('measured_moment','physical_cuff_moment_world_nm')]
        errors={}
        for source_key,trace_key in pairs:
            old=np.array([r[source_key] for r in history],float)
            actual=np.c_[z['reference_q_rad'][ids[:-1]],z['reference_dq_rad_s'][ids[:-1]]] if trace_key is None else z[trace_key][ids[:-1]]
            errors[source_key]=float(np.max(np.abs(old-actual)))
            if errors[source_key]!=0.:raise ValueError('CAUSAL_TRACE_MISMATCH:'+group+':'+source_key)
        if [r['phase'] for r in history]!=z['task_phase'][ids[:-1]].tolist():
            raise ValueError('PHASE_ALIGNMENT_MISMATCH:'+group)
        end=int(ids[-1]);completion=[r for r in summary['task']['phase_transitions'] if r['to']=='COMPLETE']
        if len(completion)!=1:raise ValueError('MISSING_CAUSAL_COMPLETION_COMMIT:'+group)
        completion=completion[0]
        if abs(float(completion['time_s'])-float(z['time_s'][end]))>1e-12:
            raise ValueError('TERMINAL_COMMIT_TIME_MISMATCH:'+group)
        if not np.array_equal(np.array(completion['estimated_state']),z['estimated_human_state_rad_rad_s'][end]):
            raise ValueError('TERMINAL_ESTIMATOR_COMMIT_MISMATCH:'+group)
        terminal=dict(time_s=float(z['time_s'][end]),phase=str(z['task_phase'][end]),
            estimated_q_dq=z['estimated_human_state_rad_rad_s'][end].tolist(),
            reference_q_dq=np.r_[z['reference_q_rad'][end],z['reference_dq_rad_s'][end]].tolist(),
            measured_force=z['physical_cuff_force_world_n'][end].tolist(),
            measured_moment=z['physical_cuff_moment_world_nm'][end].tolist(),
            source_sample_time_s=float(completion['state_source_time_s']),truth_used=False)
        rows=history+[terminal]
        # Issued first reference is already causal/public. Goal comes from the
        # frozen task config. No evaluation-only state defines progress.
        start=history[0]['reference_q_dq'][:2]
        goal=[math.radians(v) for v in case['task']['goal_deg']]
        identity=dict(case_sha256=sha(case_path),trace_sha256=sha(trace_path),
            source_history_sha256=sha(history_path),group=group,
            source='v7_exposed_cold_OUT0_complete_B_not_continuous_Trial1')
        h=ti.summarize(rows,trial_id=group+'_B',patient_id=group,trial_number=1,
            actual_action_tag='B',task_start_s=rows[0]['time_s'],task_end_s=terminal['time_s'],
            complete=True,identity=identity,public_phase_targets={'OUTBOUND':[start,goal],'RETURN':[goal,start]})
        jf_error=h['JF_N_s']-measured['J_F_N_s'];jm_error=h['JM_Nm_s']-measured['moment_integral_Nm_s']
        if abs(jf_error)>1e-6 or abs(jm_error)>1e-6:
            raise ValueError('ORIGINAL_INTEGRAL_CLOSURE_FAILED:'+group+':'+str([jf_error,jm_error]))
        names,values=ti.feature_vector(h)
        results.append(dict(group=group,history=h,feature_names=names,features=values,
            integrity=dict(original_history_rows=len(history),trace_task_boundaries=len(ids),
                exact_preterminal_field_errors=errors,original_missing_terminal_boundary=True,
                added_terminal_source_fields=permitted,terminal_source_timestamp='summary.task.phase_transitions[COMPLETE].state_source_time_s',
                terminal_estimator_commit_exact_match=True,JF_closure_error_N_s=jf_error,JM_closure_error_Nm_s=jm_error,
                public_progress_source='first_issued_causal_reference_and_frozen_case_task_goal',
                native_truth_arrays_read=False,future_task_results_as_features=False),
            scope='EXPOSED_COMPLETED_B_CONTEXT_NOT_PHYSICAL_TRIAL_ADAPTATION'))
        for file in [history_path,trace_path,summary_path,measured_path,plan_path,case_path]:
            sources.append(dict(path=str(file),sha256=sha(file),bytes=file.stat().st_size))
    result=dict(status='EXTRACTION_PASS_NO_FIT',groups=GROUPS,rows=results,sources=sources,
        feature_dim=8,context_count=6,new_independent_patients=0,all_contexts_exposed_development=True,
        fit_count=0,new_physics_attempts=0,raw_truth_feature_reads=0,
        started_unix=started,finished_unix=time.time(),process_cpu_s=time.process_time()-cpu,
        max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    path=HERE/'V7_COMPLETE_B_HISTORY8_DATASET.json'
    if path.exists():raise FileExistsError('NO_OVERWRITE:'+str(path))
    path.write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    signal.alarm(0)
    print(json.dumps(dict(status=result['status'],contexts=6,fit_count=0,new_physics=0,
        max_abs_JF_error=max(abs(r['integrity']['JF_closure_error_N_s']) for r in results),
        max_abs_JM_error=max(abs(r['integrity']['JM_closure_error_Nm_s']) for r in results),
        process_cpu_s=result['process_cpu_s'],wall_s=result['finished_unix']-started)))


if __name__=='__main__':main()
