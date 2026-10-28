"""Synthetic protocol probes, not learning data or physical evidence."""
import copy
import json
from pathlib import Path
import resource
import time

import trial_interface as t


def main():
    started=time.time(); cpu_start=time.process_time()
    rows=[]
    for i in range(31):
        phase='OUTBOUND' if i<10 else 'HOLD' if i<20 else 'RETURN'
        progress=(i%10)/9 if phase!='HOLD' else .5
        rows.append(dict(time_s=i*.005, phase=phase,
            estimated_q_dq=[0., -.001, 0., 0.], reference_q_dq=[0., 0., 0., 0.],
            measured_force=[3.,4.,0.],measured_moment=[0.,0.,2.],
            source_sample_time_s=i*.005,reference_progress=progress,truth_used=False))
    kwargs=dict(trial_id='SYNTHETIC_T1',patient_id='SYNTHETIC_ONLY',trial_number=1,
        actual_action_tag='B',task_start_s=0.,task_end_s=.15,complete=True,
        identity=dict(task='synthetic',source='synthetic',scorer='synthetic',menu='synthetic'),
        public_phase_targets={})
    summary=t.summarize(rows,**kwargs)
    checks={
        'constant_force_left_integral_closure':abs(summary['JF_N_s']-.75)<1e-12,
        'constant_moment_left_integral_closure':abs(summary['JM_Nm_s']-.3)<1e-12,
        'three_phase_duration_closure':abs(sum(v['duration_s'] for v in summary['phases'].values())-.15)<1e-12,
    }
    def rejection(name, bad_rows, bad_kwargs, expected):
        try:t.summarize(bad_rows,**bad_kwargs)
        except ValueError as e:checks[name]=str(e).startswith(expected)
        else:checks[name]=False
    rejection('partial_has_no_complete_label',rows,{**kwargs,'complete':False},'PARTIAL_TRIAL')
    rejection('missing_terminal_rejected',rows[:-1],kwargs,'MISSING_TERMINAL')
    rejection('missing_start_rejected',rows[1:],kwargs,'MISSING_TASK_START')
    bad=copy.deepcopy(rows);bad[2]['native_qpos']=[1.]
    rejection('native_truth_field_rejected',bad,kwargs,'NON_ALLOWLISTED')
    bad=copy.deepcopy(rows);bad[2]['source_sample_time_s']=1.
    rejection('future_observation_rejected',bad,kwargs,'FUTURE_OBSERVATION')
    bad=copy.deepcopy(rows);bad[2]['time_s']=bad[1]['time_s'];bad[2]['source_sample_time_s']=bad[1]['source_sample_time_s']
    rejection('nonmonotonic_time_rejected',bad,kwargs,'HISTORY_GAP')
    target=t.ilc_target(summary,window='all_phases')
    menu=[dict(tag='B',nominal_reference_delta_deg={}),
          dict(tag='DECLARED_SMALL',nominal_reference_delta_deg={'OUTBOUND':[0.,-.02],'RETURN':[0.,-.02]})]
    selected=t.project_to_menu(target,menu,menu_sha256='synthetic_menu_hash')
    checks['projection_only_returns_existing_tag']=selected['selected_tag'] in [d['tag'] for d in menu]
    checks['projection_makes_no_new_action']=selected['new_continuous_action_created'] is False
    t.verify_trial2_inputs(summary,patient_id='SYNTHETIC_ONLY',trial_number=2,
        frozen_at_s=2.,source_trial_completed_at_s=1.,expected_identity=kwargs['identity'])
    try:
        t.verify_trial2_inputs(summary,patient_id='OTHER',trial_number=2,
            frozen_at_s=2.,source_trial_completed_at_s=1.,expected_identity=kwargs['identity'])
    except ValueError as e:checks['other_patient_history_rejected']=str(e)=='WRONG_PATIENT_OR_PREVIOUS_TRIAL'
    else:checks['other_patient_history_rejected']=False
    result=dict(status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
        evidence_class='SYNTHETIC_SOFTWARE_PROTOCOL_ONLY',physical_level1_pass=False,
        learning_valid=False,task_valid=False,physics_attempts=0,training_runs=0,
        model_checkpoints_created=0,synthetic_rows_used_as_learning_data=0,
        started_unix=started,finished_unix=time.time(),process_cpu_s=time.process_time()-cpu_start,
        max_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    path=Path(__file__).with_name('INTERFACE_CHECK_v2.json')
    if path.exists():raise FileExistsError('PRESERVE_EXISTING_CHECK')
    path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps(result))
    if result['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
