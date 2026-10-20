"""Offline synthetic check of report denominators and additive launcher gate."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('report_tables',ROOT/'report_tables.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def put(root,name,obj):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj))
with tempfile.TemporaryDirectory(prefix='ihear_report_offline_synthetic_') as folder:
    root=Path(folder)
    put(root,'VIRTUAL_PATIENT_COHORT.json',{'patients':[{'patient_id':f'P{i:02d}','label':'SYNTHETIC_ONLY'} for i in range(5)]})
    for i,gain in enumerate([2.,-3.,4.,9.]):
        pid=f'P{i:02d}';full=i!=3;qualified=i in [0,2];evaluations={}
        for arm in ['B','H150']:
            ident=pid+'_'+arm
            evaluations[arm]={'id':ident,'complete_task':full,'integration':'PASS' if full else 'INCOMPLETE',
                'axes':{'task':'PASS' if full else 'FAIL','absolute_safety':'FAIL' if i==1 else 'PASS','causal_execution':'PASS'},
                'absolute_task_execution_qualified':qualified,'qualification':'COMPLETE_QUALIFIED_PASS' if qualified else 'FAIL',
                'J_F_N_s':100. if arm=='B' else 100.-gain,'motion_comparison':{'acceptance_pass':qualified,'failed_requirements':[]},
                'motion_extra':{'outbound_overshoot_deg':[.1,.2],'return_undershoot_deg':[.3,.4]}}
            if not full:
                evaluations[arm].update(abort_reason='SYNTHETIC_TASK_ABORT',observed_prefix={'observed_task_duration_s':17.545,'observed_task_J_F_N_s':1583.},
                    interventions={'status':'FAIL','incomplete_task_missing_interventions':True})
                evaluations[arm]['axes'].update(causal_execution='FAIL',causal_execution_checks={'native_receipt_ownership':None,'scientific_request_version_age_valid':False},
                    original_evaluator={'scientific_validity':{'status':'FAIL','reasons':['request_19:request_not_activated']}})
            put(root,f'reports/{ident}_MEASURED.json',{'J_F_N_s':999,'force_peak_N':10,'tracking_RMS_deg':[.01,.02],
                'dose':{'excursion_deg':[110,111]},'phase_cost':{'phases':{'OUTBOUND':{'J_F_N_s':50}}},
                'native_physical_audit':{'unchanged_evaluator':{'raw_scorer_v2':{'peak_robot_torque_fraction':.4,'minimum_true_shank_clearance_m':.01}}}})
            put(root,f'source/results/{ident}/summary.json',{'status':'COMPLETE','execution_mode':'SCIENTIFIC_SIMULATION'})
            if not (i==2 and arm=='H150'):
                put(root,f'source/results/{ident}/HIGH_ROM_CASE_RESULT.json',{'status':'COMPLETE','execution_mode':'SCIENTIFIC_SIMULATION'})
            put(root,f'derived/{ident}_INDEPENDENT.json',{'status':'PASS'})
        put(root,f'{pid}_COMPARISON.json',dict(evaluations,full_integral_comparison_valid=full,qualified_B_reference=qualified,
            complete_qualified_H150=qualified,pair_identity_valid=True,gain_percent=gain,gain_N_s=gain))
        put(root,f'{pid}_PAIR_GATE.json',{'status':'PASS'})
    result,markdown=module.build(root)
    assert len(result['rows'])==5 and len(result['arm_rows'])==10
    assert result['comparisons']['all_valid_pairs']['gain_denominator']==3
    assert result['comparisons']['all_valid_pairs']['equal_patient_mean_gain_percent']==1.
    assert result['comparisons']['new_patients_valid_pairs']['registered_denominator']==4
    assert result['comparisons']['new_patients_valid_pairs']['equal_patient_mean_gain_percent']==.5
    assert result['comparisons']['final_complete_qualified_pairs']['patient_ids']==['P00']
    assert result['comparisons']['new_patients_final_complete_qualified_pairs']['gain_denominator']==0
    assert result['launcher_gate']['status']=='UNKNOWN'
    assert result['launcher_gate']['nonpass_required_run_ids']==['P02_H150']
    assert result['rows'][2]['final_complete_qualified_pair'] is None
    assert result['rows'][3]['B']['J_F_N_s'] is None and result['rows'][3]['gain_percent'] is None
    assert result['rows'][3]['B']['observed_prefix_J_F_N_s']==1583.
    assert result['rows'][3]['B']['absolute_safety_scope']=='OBSERVED_PREFIX_ONLY'
    assert 'PASS(prefix only)' in markdown and 'FAIL(request gate)' in markdown
    assert result['rows'][4]['final_complete_qualified_pair'] is None
    assert result['rows'][1]['motion_relative']=='NOT_EVALUABLE_INVALID_B'
    assert result['rows'][4]['motion_relative']=='NOT_EVALUABLE'
    assert result['rows'][0]['B']['phases']['OUTBOUND']['actual_phase_clock_duration_s'] is None
    assert result['rows'][0]['B']['peak_robot_torque_fraction']==.4
    assert result['rows'][0]['B']['outbound_overshoot_from_actual_issued_reference_deg']==[.1,.2]
    assert 'P04' in markdown and 'NA' in markdown
    json.dumps(result,allow_nan=False)
    report={'status':'PASS','scope':'SYNTHETIC_ONLY_NOT_RESEARCH_RESULTS','tests':['all_registered_rows','reference_excluded_new_patient_subset',
        'equal_patient_valid_vs_qualified_denominators','missing_launcher_blocks_promotion','partial_integrals_not_full','invalid_baseline_retained',
        'actual_keys_and_missing_durations_preserved','aborted_prefix_safety_scope_and_request_failure','JSON_and_markdown'],'physics_starts':0}
    put(ROOT,'audit_protocol/REPORT_TABLES_SYNTHETIC_VALIDATION.json',report)
    print(json.dumps(report))
