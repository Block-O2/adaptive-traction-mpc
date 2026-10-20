"""Pure offline report tables from saved evidence; never imports execution code."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import statistics
import sys
sys.dont_write_bytecode=True
from aggregate_delivery import Evidence, execution_evidence, interpret_arm_evidence, separate_motion_contract, write_json

PHASES=('OUTBOUND','HOLD','RETURN')

def get(obj,*keys):
    for key in keys:
        if not isinstance(obj,dict):return None
        obj=obj.get(key)
    return obj

def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def describe(rows,registered):
    valid=[r for r in rows if finite(r.get('gain_percent'))]
    gains=[r['gain_percent'] for r in valid]
    deltas=[r['gain_N_s'] for r in valid if finite(r.get('gain_N_s'))]
    return dict(registered_denominator=registered,observed_pair_denominator=len(rows),gain_denominator=len(gains),
        patient_ids=[r['patient_id'] for r in valid],missing_gain_patient_ids=[r['patient_id'] for r in rows if not finite(r.get('gain_percent'))],
        equal_patient_mean_gain_percent=statistics.mean(gains) if gains else None,
        median_gain_percent=statistics.median(gains) if gains else None,
        minimum_gain_percent=min(gains) if gains else None,maximum_gain_percent=max(gains) if gains else None,
        positive_gain_patients=sum(x>0 for x in gains),zero_gain_patients=sum(x==0 for x in gains),negative_gain_patients=sum(x<0 for x in gains),
        equal_patient_mean_gain_N_s=statistics.mean(deltas) if deltas else None,
        delta_force_integral_denominator=len(deltas),weighting='One equal weight per patient; no repetitions or trace-row weighting.')

def launcher_check(ev,ident,claimed):
    rel=f'source/results/{ident}/HIGH_ROM_CASE_RESULT.json'
    launch=ev.read(rel);summary=ev.read(f'source/results/{ident}/summary.json')
    a=get(launch,'status');b=get(summary,'status')
    modes=(get(launch,'execution_mode'),get(summary,'execution_mode'))
    complete=a=='COMPLETE' and b=='COMPLETE'
    mode_match=all(x=='SCIENTIFIC_SIMULATION' for x in modes)
    status='UNKNOWN' if launch is None or summary is None else 'PASS' if complete and mode_match else 'FAIL'
    return dict(run_id=ident,source_claimed_qualified=claimed,status=status,launcher_status=a,summary_status=b,
        launcher_execution_mode=modes[0],summary_execution_mode=modes[1],both_complete=complete,
        scientific_execution_mode_match=mode_match,source=ev.artifact(rel),summary_source=ev.artifact(f'source/results/{ident}/summary.json'),
        rule='Original launcher status COMPLETE and summary status COMPLETE are both required. This additive gate never changes frozen evaluation bytes.')

def build(package):
    ev=Evidence(package);cohort=ev.read('VIRTUAL_PATIENT_COHORT.json',{})
    rows=[];arms=[];launchers=[];source=[]
    for patient in cohort.get('patients',[]):
        pid=patient['patient_id'];pair=ev.read(f'{pid}_COMPARISON.json')
        if pair is None:pair=ev.read(f'reports/{pid}_PAIR_ANALYSIS.json')
        pair=pair or {};gate=ev.read(f'{pid}_PAIR_GATE.json',{})
        evaluated={arm:pair.get(arm) or ev.read(f'reports/{pid}_{arm}_CROSS_EVALUATION.json',{}) for arm in ['B','H150']}
        motion=separate_motion_contract(pair if pair else None,evaluated['H150'])
        patient_arms={}
        source.extend([ev.artifact(f'{pid}_COMPARISON.json'),ev.artifact(f'{pid}_PAIR_GATE.json')])
        for arm in ['B','H150']:
            ident=pid+'_'+arm;evaluation=evaluated[arm];measured=ev.read(f'reports/{ident}_MEASURED.json',{})
            extra=evaluation.get('motion_extra') or {};dose=measured.get('dose') or {}
            raw_scorer=get(measured,'native_physical_audit','unchanged_evaluator','raw_scorer_v2') or get(evaluation,'axes','original_evaluator','raw_scorer_v2') or {}
            interpretation=interpret_arm_evidence(evaluation);observed=evaluation.get('observed_prefix') or {}
            partial_execution=execution_evidence(ev,ident) if evaluation.get('complete_task') is False else None
            claimed=evaluation.get('absolute_task_execution_qualified') is True if arm=='B' else pair.get('complete_qualified_H150') is True
            launch=launcher_check(ev,ident,claimed);launchers.append(launch)
            audit=ev.read(f'derived/{ident}_INDEPENDENT_FAILURE.json') or ev.read(f'derived/{ident}_INDEPENDENT.json')
            full=evaluation.get('complete_task') is True and evaluation.get('integration')=='PASS'
            phase_cost=measured.get('phase_cost') or evaluation.get('phase_cost') or {}
            phases={}
            for phase in PHASES:
                cost=get(phase_cost,'phases',phase) or {}
                duration=get(measured,'phase_durations',phase)
                if duration is None:duration=get(evaluation,'phase_durations',phase)
                jf=cost.get('J_F_N_s');total=evaluation.get('J_F_N_s') if full else None
                phases[phase]=dict(actual_phase_clock_duration_s=duration,integrated_trace_duration_s=cost.get('integrated_trace_duration_s'),
                    J_F_N_s=jf,moment_integral_Nm_s=cost.get('moment_integral_Nm_s'),mean_force_N=cost.get('mean_force_N'),
                    force_peak_N=cost.get('force_peak_N'),force_contribution_percent=100*jf/total if finite(jf) and finite(total) and total>0 else None)
            armrow=dict(patient_id=pid,label=patient.get('label'),arm=arm,run_id=ident,
                evidence_status=evaluation.get('evidence_level'),complete_task=evaluation.get('complete_task'),integration=evaluation.get('integration'),
                measurement_scope='FULL_TASK_INTEGRAL_CLOSURE_PASS' if full else 'PARTIAL_OR_UNAVAILABLE_NOT_A_FULL_TASK_INTEGRAL',
                evidence_interpretation=interpretation,absolute_safety_scope=interpretation['absolute_safety_scope'],abort_reason=evaluation.get('abort_reason'),
                partial_raw_runtime_execution_evidence=partial_execution,
                observed_prefix_duration_s=observed.get('observed_task_duration_s'),observed_prefix_J_F_N_s=observed.get('observed_task_J_F_N_s'),
                observed_prefix_moment_integral_Nm_s=observed.get('observed_task_moment_integral_Nm_s'),
                task=get(evaluation,'axes','task'),absolute_safety=get(evaluation,'axes','absolute_safety'),causal_execution=get(evaluation,'axes','causal_execution'),
                frozen_qualification=evaluation.get('qualification'),failure_labels=evaluation.get('labels'),
                launcher_complete_gate=launch['status'],independent_verification=get(audit,'status'),
                J_F_N_s=evaluation.get('J_F_N_s') if full else None,
                moment_integral_Nm_s=measured.get('moment_integral_Nm_s') if full else None,
                force_peak_N=measured.get('force_peak_N') if measured.get('force_peak_N') is not None else observed.get('force_peak_N'),
                moment_peak_Nm=measured.get('moment_peak_Nm') if measured.get('moment_peak_Nm') is not None else observed.get('moment_peak_Nm'),
                tracking_RMS_deg=measured.get('tracking_RMS_deg'),excursion_deg=dose.get('excursion_deg'),cumulative_travel_deg=dose.get('cumulative_travel_deg'),
                outbound_overshoot_from_actual_issued_reference_deg=extra.get('outbound_overshoot_deg'),
                return_undershoot_from_actual_issued_reference_deg=extra.get('return_undershoot_deg'),
                return_terminal_signed_error_from_actual_issued_reference_deg=extra.get('return_terminal_error_from_issued_reference_deg'),
                final_issued_outbound_reference_deg=extra.get('final_issued_outbound_reference_deg'),final_issued_return_reference_deg=extra.get('final_issued_return_reference_deg'),
                outbound_overshoot_from_nominal_goal_deg=extra.get('outbound_overshoot_from_nominal_goal_deg'),
                return_undershoot_from_nominal_start_deg=extra.get('return_undershoot_from_nominal_start_deg'),
                native_velocity_peak_deg_s=get(measured,'motion','raw','full','velocity_deg_s','max_abs'),
                native_acceleration_peak_deg_s2=get(measured,'motion','raw','full','acceleration_deg_s2','max_abs'),
                native_jerk_peak_deg_s3=get(measured,'motion','raw','full','jerk_deg_s3','max_abs'),
                actual_task_duration_s=dose.get('duration_s'),phase_cost_status=phase_cost.get('status'),phase_cost_closure_error_N_s=phase_cost.get('closure_error_N_s'),phases=phases,
                peak_robot_torque_fraction=raw_scorer.get('peak_robot_torque_fraction'),
                minimum_true_shank_clearance_m=raw_scorer.get('minimum_true_shank_clearance_m'),
                minimum_session_shank_clearance_m=raw_scorer.get('minimum_session_shank_clearance_m'),
                minimum_measured_sleeve_gap_m=raw_scorer.get('minimum_measured_sleeve_gap_m'),
                absolute_common_conditions=raw_scorer.get('conditions'),
                measured_source=ev.artifact(f'reports/{ident}_MEASURED.json'),evaluation_source=ev.artifact(f'reports/{ident}_CROSS_EVALUATION.json'))
            patient_arms[arm]=armrow;arms.append(armrow)
        valid=pair.get('full_integral_comparison_valid') is True
        reported=pair.get('complete_qualified_H150') is True
        independent=all(patient_arms[a]['independent_verification']=='PASS' for a in ['B','H150']) and gate.get('status')=='PASS'
        launch_pass=all(patient_arms[a]['launcher_complete_gate']=='PASS' for a in ['B','H150'])
        final_qualified=(valid and reported and independent and launch_pass) if pair else None
        if reported and not final_qualified and (any(patient_arms[a]['launcher_complete_gate']=='UNKNOWN' for a in ['B','H150']) or any(patient_arms[a]['independent_verification'] is None for a in ['B','H150'])):
            final_qualified=None
        rows.append(dict(patient_id=pid,label=patient.get('label'),reference_patient=pid=='P00',future_learning_split=patient.get('future_learning_split'),
            full_integral_comparison_valid=valid,qualified_B_reference=pair.get('qualified_B_reference'),
            gain_percent=pair.get('gain_percent') if valid else None,gain_N_s=pair.get('gain_N_s') if valid else None,
            reported_complete_qualified_H150=reported,independent_pair_verification=independent,final_launcher_pair_gate=launch_pass,
            final_complete_qualified_pair=final_qualified,motion_relative=motion['relative_contract_status'],motion_contract_separation=motion,
            invalid_baseline_warning=pair.get('warning'),descriptive_gain_only=valid and not final_qualified,B=patient_arms['B'],H150=patient_arms['H150']))
    valid=[r for r in rows if r['full_integral_comparison_valid']]
    qualified=[r for r in rows if r['final_complete_qualified_pair'] is True]
    required=[x for x in launchers if x['source_claimed_qualified']]
    final_check='FAIL' if any(x['status']=='FAIL' for x in required) else 'UNKNOWN' if any(x['status']=='UNKNOWN' for x in required) else 'PASS' if required else 'NOT_EVALUABLE'
    result=dict(schema='IHEAR_REPORT_STATISTICS_V1',snapshot_status='FINAL_DISPATCH_FILE_PRESENT' if (Path(package)/'SERIAL_CAMPAIGN_DONE.json').exists() else 'PROVISIONAL_EXECUTION_NOT_DECLARED_FINISHED',
        generated_utc=datetime.now(timezone.utc).isoformat(),registered_patient_count=len(rows),registered_new_patient_count=sum(r['patient_id']!='P00' for r in rows),
        comparisons=dict(all_valid_pairs=describe(valid,len(rows)),new_patients_valid_pairs=describe([r for r in valid if r['patient_id']!='P00'],sum(r['patient_id']!='P00' for r in rows)),
            final_complete_qualified_pairs=describe(qualified,len(rows)),new_patients_final_complete_qualified_pairs=describe([r for r in qualified if r['patient_id']!='P00'],sum(r['patient_id']!='P00' for r in rows))),
        rows=rows,arm_rows=arms,launcher_gate=dict(status=final_check,source_claimed_qualified_arm_denominator=len(required),checks=launchers,
            nonpass_required_run_ids=[x['run_id'] for x in required if x['status']!='PASS']),
        sources=dict(cohort=ev.artifact('VIRTUAL_PATIENT_COHORT.json'),patient_pairs=source),read_errors=ev.read_errors,
        interpretation='Exploratory preregistered engineering sensitivity cohort, not a clinical distribution. Equal-patient descriptive statistics only. P00 is a reference regression and is excluded from the separately labelled new-patient summaries.',
        measurement_notes=['Null means missing/not evaluable; no planned phase timing or zero is substituted.',
            'Full-task JF appears only after completion and integral closure. Valid full integrals from unqualified pairs remain descriptive and do not imply safe improvement.',
            'Joint arrays are [hip,knee]. Tracking RMS is the saved native measurement against the emitted reference, distinct from compact STATE_ACTION tracking against a request/handoff reference.',
            'Under/overshoot uses actual final issued phase references; nominal-target deviations remain separate JSON fields.',
            'Phase contribution is phase JF divided by that arm full TASK JF; phase durations use observed boundaries.',
            'Torque fraction and clearance are copied from the original scorer common-condition evidence. No absent physical safety value is inferred from PASS.',
            'For an aborted arm, safety PASS means only the observed prefix. A causal/scientific request gate failure does not prove native receipts are corrupted; null receipt-ownership checks remain unknown.',
            'An independent PARTIAL_RAW_OWNERSHIP_PASS can verify recorded receipt/native evidence without promoting scientific task success. TRACK command mode can follow an escape reference; explicit FALLBACK_COMMITTED events are separately retained.',
            'Future reserved patient identities are exposed in this descriptive study; new untouched identities are needed if their outcomes influence learning design.',
            'Raw receipt native-step totals include inherited prefixes; unique physics work belongs to ATTEMPT_ACCOUNTING.json.'],
        physics_started_by_reporting=0,training_performed=False,frozen_evaluations_modified=False)
    return result,render(result)

def cell(value,places=3):
    if value is None:return 'NA'
    if isinstance(value,bool):return 'yes' if value else 'no'
    if isinstance(value,int):return str(value)
    if isinstance(value,(list,tuple)):return '['+', '.join(cell(x,places) for x in value)+']'
    if finite(value):return f'{value:.{places}f}'
    return str(value).replace('|','\\|').replace('\n',' ')

def table(headers,body):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(cell(x) for x in row)+' |' for row in body])+'\n'

def axis_display(row,key):
    value=row.get(key)
    if key=='absolute_safety' and value=='PASS' and row.get('complete_task') is False:return 'PASS(prefix only)'
    if key=='causal_execution' and value=='FAIL' and get(row,'evidence_interpretation','causal_execution_source_checks','scientific_request_version_age_valid') is False:return 'FAIL(request gate)'
    return cell(value)

def render(result):
    out=['# Cross-patient B/H150 report tables','',f"Snapshot: {result['snapshot_status']}. Generated {result['generated_utc']}.",'',
         f"All {result['registered_patient_count']} registered identities are retained. P00 is the reference regression; the new-patient denominator is {result['registered_new_patient_count']}. NA denotes missing or not evaluable, never zero.",'',
         'These are descriptive engineering sensitivity results, with equal weight per patient and no clinical-population inference. Full qualification below additionally requires independent evidence, matching pair gate, and original launcher + summary COMPLETE for both arms. Frozen evaluation bytes remain unchanged.','',
         '## Equal-patient gain summaries','']
    out.append(table(['Subset','Registered','Observed n','Mean gain %','Median %','Min %','Max %','Positive / zero / negative'],[
        [name,s['registered_denominator'],s['gain_denominator'],s['equal_patient_mean_gain_percent'],s['median_gain_percent'],s['minimum_gain_percent'],s['maximum_gain_percent'],f"{s['positive_gain_patients']} / {s['zero_gain_patients']} / {s['negative_gain_patients']}"] for name,s in result['comparisons'].items()]))
    out+=['Only full-integral-comparable pairs enter valid-pair means. An invalid B reference makes relative motion not evaluable; its complete integrals, if any, remain descriptive.','',
          '## Registered patient outcomes','',table(['Patient','B JF (N s)','H150 JF (N s)','Gain %','B task/safety/causal','H task/safety/causal','Relative motion','B/H launcher gate','Final qualified'],[
              [r['patient_id'],r['B']['J_F_N_s'],r['H150']['J_F_N_s'],r['gain_percent'],' / '.join(axis_display(r['B'],k) for k in ['task','absolute_safety','causal_execution']),
               ' / '.join(axis_display(r['H150'],k) for k in ['task','absolute_safety','causal_execution']),r['motion_relative'],r['B']['launcher_complete_gate']+' / '+r['H150']['launcher_complete_gate'],r['final_complete_qualified_pair']] for r in result['rows']]),
          '## Incomplete executions and observed prefixes','',
          'Prefix integrals below are explicitly excluded from full-task JF and gain. Safety PASS applies only to the recorded prefix. A task abort is not a model-invalid classification; request/activation failures and incomplete H150 intent do not establish native-receipt corruption.','',
          table(['Run','Abort reason','Prefix duration s','Prefix JF N s (not full task)','Safety scope','Original ownership check','Independent prefix ownership','Fallback commit observed','Original scientific reasons','Missing interventions due to incomplete task'],[
              [r['run_id'],r['abort_reason'],r['observed_prefix_duration_s'],r['observed_prefix_J_F_N_s'],axis_display(r,'absolute_safety'),
               get(r,'evidence_interpretation','native_receipt_ownership_source_check'),get(r,'partial_raw_runtime_execution_evidence','independent_partial_native_ownership','status'),
               get(r,'partial_raw_runtime_execution_evidence','explicit_fallback_commit_event_observed'),get(r,'evidence_interpretation','original_scientific_validity_reasons'),
               get(r,'evidence_interpretation','incomplete_task_missing_interventions')] for r in result['arm_rows'] if r['complete_task'] is False]),
          '## Force, moment, tracking and actual-reference motion','',
          'Joint pairs are [hip, knee]. Overshoot is OUTBOUND above its final issued reference; undershoot is RETURN below its final issued reference. Nominal targets are retained separately in JSON.','',
          table(['Patient / arm','Coverage','Force peak N','Moment integral N m s','Moment peak N m','Tracking RMS deg','Outbound overshoot deg','Return undershoot deg','Excursion deg'],[
              [r['run_id'],r['absolute_safety_scope'],r['force_peak_N'],r['moment_integral_Nm_s'],r['moment_peak_Nm'],r['tracking_RMS_deg'],r['outbound_overshoot_from_actual_issued_reference_deg'],r['return_undershoot_from_actual_issued_reference_deg'],r['excursion_deg']] for r in result['arm_rows']]),
          '## Actual phase timing and force-integral contributions','',
          'Each phase cell is actual duration (s) / force integral (N s) / share of that arm full-task JF (%). Values come from observed phase boundaries, not the planned schedule.','',
          table(['Patient / arm','Task duration s','OUTBOUND: s / N s / %','HOLD: s / N s / %','RETURN: s / N s / %','Closure'],[
              [r['run_id'],r['actual_task_duration_s']]+[' / '.join(cell(r['phases'][phase][key]) for key in ['actual_phase_clock_duration_s','J_F_N_s','force_contribution_percent']) for phase in PHASES]+[r['phase_cost_status']] for r in result['arm_rows']]),
          '## Saved absolute-safety measurements','',
          table(['Patient / arm','Peak robot torque fraction','True shank clearance m','Session shank clearance m','Measured sleeve gap m','Safety gate and coverage'],[
              [r['run_id'],r['peak_robot_torque_fraction'],r['minimum_true_shank_clearance_m'],r['minimum_session_shank_clearance_m'],r['minimum_measured_sleeve_gap_m'],axis_display(r,'absolute_safety')] for r in result['arm_rows']]),
          '## Additive original-launcher qualification check','',
          f"Status: {result['launcher_gate']['status']}; source-claimed qualified arm denominator: {result['launcher_gate']['source_claimed_qualified_arm_denominator']}. Non-pass required runs: {', '.join(result['launcher_gate']['nonpass_required_run_ids']) or 'none'}.",'',
          'The exact source is source/results/{run_id}/HIGH_ROM_CASE_RESULT.json::status. The helper requires launcher status COMPLETE, summary status COMPLETE, and matching SCIENTIFIC_SIMULATION mode before final promotion. Missing launch evidence stays UNKNOWN. All original evaluations remain unchanged.','',
          '## Interpretation limits','']
    out += ['- '+note for note in result['measurement_notes']]
    return '\n'.join(out)+'\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args();result,markdown=build(args.package)
    write_json(args.package/'derived/REPORT_STATISTICS.json',result)
    path=args.package/'analysis/REPORT_TABLES.md';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(markdown,encoding='utf-8')
    print({'status':'OFFLINE_REPORT_TABLES_WRITTEN','registered':result['registered_patient_count'],'valid_pairs':result['comparisons']['all_valid_pairs']['gain_denominator'],
           'new_valid_pairs':result['comparisons']['new_patients_valid_pairs']['gain_denominator'],'qualified_pairs':result['comparisons']['final_complete_qualified_pairs']['gain_denominator'],
           'launcher_gate':result['launcher_gate']['status'],'read_errors':len(result['read_errors']),'physics_starts':0})

if __name__=='__main__':main()
