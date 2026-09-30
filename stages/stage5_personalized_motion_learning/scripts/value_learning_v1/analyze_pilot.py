"""Retrospective development convergence; thresholds frozen only after pilot."""
from datetime import datetime,timezone
import json
import numpy as np
from scipy.stats import spearmanr
from research_campaign import D,save,sha

def summary(values):
 values=[float(x) for x in values if x is not None and np.isfinite(x)]
 if not values:return {'count':0}
 return {'count':len(values),'median':float(np.median(values)),
  'p95':float(np.percentile(values,95)),'p99':float(np.percentile(values,99)),'maximum':float(np.max(values))}

def q_stability(a,b):
 if not a or not b:return None
 keys=sorted(set(a)&set(b))
 if len(keys)<3:return None
 x=np.array([a[k] for k in keys]);y=np.array([b[k] for k in keys])
 if np.ptp(x)<1e-10 or np.ptp(y)<1e-10:return None
 return float(spearmanr(x,y).statistic)

def main():
 pilot=json.loads((D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json').read_text())
 matched=json.loads((D/'KNOWN_BENEFIT_CAPTURE.json').read_text())
 absolute=json.loads((D/'PRIMARY_OBJECTIVE_KNOWN_BENEFIT_CAPTURE.json').read_text())
 offline=json.loads((D/'OFFLINE_VALUE_MODEL_COMPARISON.json').read_text())
 latency_gate=json.loads((D/'ONLINE_LATENCY_PROMOTION_GATE.json').read_text())
 ranges=[];range_sources=[]
 for row in matched['rows']:
  values=[p['J_F_n_s'] for p in row.get('targeted_safe_alternatives',[]) if p['status']=='VALID']
  if len(values)>=2:
   width=float(np.ptp(values));ranges.append(width)
   range_sources.append({'session':row['session'],'attempt':row['repetition'],'range_n_s':width})
 local_scale=float(np.median(ranges)) if ranges else None
 # This is development-derived and retrospective. No decisions in this pilot
 # use these thresholds. A later experiment must freeze them before execution.
 tolerance=None if local_scale is None else .1*local_scale
 threshold={'schema':'provisional_after_development_v1','status':'FROZEN_AFTER_PILOT',
  'timestamp_utc':datetime.now(timezone.utc).isoformat(),'pilot_sha256':sha(D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json'),
  'source':'observed post-pilot common-start safe-alternative full-task cost ranges; not held-out test tuning',
  'source_probe_ranges':range_sources,'repeated_fresh_states_not_independent_subjects':True,
  'continuous_learning_threshold_calibration':'NOT_ESTABLISHED_NATIVE_START_GUARD_BLOCKER',
  'observed_local_action_range_median_n_s':local_scale,'performance_tolerance_n_s':tolerance,
  'tolerance_rule':'10% of observed post-pilot alternate-action range, exploratory sensitivity scale; not a statistically calibrated continuous-convergence threshold',
  'recent_window':3,'required_same_selected_descriptor_in_recent_window':True,
  'required_rank_spearman_in_recent_window':.9,'required_targeted_probe_at_evaluated_repetition':True,
  'required_conditional_reference_regret_at_most_tolerance':True,
  'required_all_recent_valid':True,'five_repetition_forced_freeze':False,
  'required_scientific_computation_plausible_gate':True,
  'first_stationary_adapter_ceiling_ms':100.,
  'computation_limit':'initial adapter timing and separate full-profile plausible-path gate; no wall-causal/hardware realtime qualification',
  'future_use':'must be prospectively frozen and independently evaluated; current triggers are retrospective only'}
 save(D/'PROVISIONAL_CONVERGENCE_THRESHOLDS.json',threshold)
 sessions=[]
 for session in pilot['sessions']:
  anchors={r['repetition']:r for r in matched['rows'] if r['session']==session['session']}
  native={r['repetition']:r for r in absolute['rows'] if r['session']==session['session']}
  rows=session['rows'];evaluated=[];first_trigger=None
  qmaps=[]
  for row in rows:
   q=row.get('candidate_Q_at_first_decision');labels=row.get('candidate_labels_at_first_decision')
   qmaps.append(None if q is None or labels is None else dict(zip(labels,q)))
  for index,row in enumerate(rows):
   rep=row['repetition_index'];recent=rows[max(0,index-2):index+1]
   same_continuous_segment=(len(recent)==3 and all(r.get('start_native_state_evaluation_only') is not None for r in recent[1:]))
   valid=(len(recent)==3 and all(r['status']=='VALID' for r in recent) and same_continuous_segment)
   recent_anchors=[anchors.get(r['repetition_index']) for r in recent]
   comparable=valid and all(a and a['status']=='VALID' for a in recent_anchors)
   gains=[] if not comparable else [a['baseline_J_F_n_s']-a['learned_J_F_n_s'] for a in recent_anchors]
   gain_span=None if not gains else float(np.ptp(gains))
   descriptor_stable=valid and len({json.dumps(r.get('selected_continuation'),sort_keys=True) for r in recent})==1
   ranking=[q_stability(qmaps[j-1],qmaps[j]) for j in range(max(1,index-1),index+1)]
   rank_stable=len(ranking)==2 and all(v is not None and v>=.9 for v in ranking)
   anchor=anchors.get(rep,{})
   probes=anchor.get('targeted_safe_alternatives',[])
   valid_probes=[p for p in probes if p['status']=='VALID']
   max_probe_gain=None if not valid_probes else max(p['improvement_over_selected_n_s'] for p in valid_probes)
   no_probe_improvement=(bool(valid_probes) and tolerance is not None and max_probe_gain<=tolerance)
   plateau=gain_span is not None and tolerance is not None and gain_span<=tolerance
   regret=anchor.get('reference_regret_n_s')
   strong=regret is not None and tolerance is not None and regret<=tolerance
   computation_plausible=(latency_gate.get('status')=='PASS' and valid and all(
    r.get('first_decision_latency',{}).get('decision_total_ms',float('inf'))<100. for r in recent))
   trigger=valid and descriptor_stable and rank_stable and plateau and no_probe_improvement and strong and computation_plausible
   if trigger and first_trigger is None:first_trigger=rep
   evaluated.append({'repetition':rep,'status':row['status'],'executed_J_F_n_s':row.get('J_F_task_n_s'),
    'baseline_adjusted_recent_benefit_span_n_s':gain_span,'conditional_reference_regret_n_s':regret,
    'conditional_known_benefit_capture':anchor.get('known_benefit_capture'),
    'absolute_native_known_benefit_capture':native.get(rep,{}).get('known_benefit_capture'),
    'value_prediction_error_n_s':row.get('first_decision_prediction_error_n_s'),
    'recent_descriptor_stable':descriptor_stable,'recent_Q_ranking_spearman':ranking,
    'recent_rank_stable':rank_stable,'baseline_adjusted_performance_plateau':plateau,
    'valid_targeted_probe_count':len(valid_probes),'maximum_targeted_probe_improvement_n_s':max_probe_gain,
    'no_large_targeted_probe_improvement':no_probe_improvement,'near_conditional_best_known':strong,
    'scientific_computation_plausible':computation_plausible,
    'retrospective_convergence_candidate':trigger,'recent_three_valid_in_same_continuous_segment':valid,
    'missing_probe_cannot_be_claimed_convergence':not bool(valid_probes)})
  unique_updates={u['path']:u for u in session['training_updates'] if u.get('path') and u.get('wall_s') is not None}
  valid_indexes=[j for j,r in enumerate(rows) if r['status']=='VALID']
  valid_rank_changes=[{'from_attempt':rows[a]['repetition_index'],'to_attempt':rows[b]['repetition_index'],'spearman':q_stability(qmaps[a],qmaps[b]),'different_fresh_segments_cannot_establish_continuous_ranking_stability':rows[b].get('start_native_state_evaluation_only') is None} for a,b in zip(valid_indexes,valid_indexes[1:])]
  sessions.append({'session':session['session'],'mode':session['mode'],'retrospective_first_trigger_repetition':first_trigger,
   'rows':evaluated,'five_rep_target_supported':any(r['retrospective_convergence_candidate'] and r['repetition']<=5 for r in evaluated),
   'fresh_development_segments':sum(r['status']=='VALID' and r.get('start_native_state_evaluation_only') is None for r in rows),
   'successive_valid_attempt_Q_rank_correlations':valid_rank_changes,
   'continuous_8_valid_repetitions_demonstrated':len(rows)==8 and all(r['status']=='VALID' for r in rows) and all(r.get('start_native_state_evaluation_only') is not None for r in rows[1:]),
   'model_update_wall_s':summary([u['wall_s'] for u in unique_updates.values()]),
   'scientific_harness_inter_rep_processing_wall_s':summary([r.get('scientific_harness_inter_rep_processing_wall_s') for r in rows]),
   'prediction_error_n_s':summary([r.get('first_decision_prediction_error_n_s') for r in rows]),
   'first_decision_adapter_latency_ms':summary([r.get('first_decision_latency',{}).get('decision_total_ms') for r in rows]),
   'valid_repetitions':sum(r['status']=='VALID' for r in rows),'attempted_repetitions':len(rows)})
 output={'status':'COMPLETE','thresholds':threshold,'sessions':sessions,
  'pilot_scope':'conditional matched scheduling and initial next-target/declared-continuation ranking; later execution stays closed loop',
  'absolute_objective_evidence':'see PRIMARY_OBJECTIVE_KNOWN_BENEFIT_CAPTURE.json; a conditional plateau alone does not establish primary-objective competitiveness',
  'inference_limits':['two single-condition development attempts, at most eight attempted repetitions each; native start failures and fresh segments are not eight continuous valid repetitions or a subject-level sample',
   'targeted probes at rep1/3/5/8; other repetitions with no probe cannot trigger convergence',
   'candidate sets and continuations are bounded; reference remains best-known, not globally optimal',
   'observed timing does not qualify hardware or realtime behavior']}
 save(D/'CONVERGENCE_ANALYSIS.json',output)
 (D/'CONVERGENCE_ANALYSIS.md').write_text('# Development convergence evidence\n\n'+json.dumps(output,indent=2)+'\n')
 scratch=json.loads((D/'SCRATCH_VS_PRIOR_ANALYSIS.json').read_text())
 scratch['observed_convergence_and_update_summary']=sessions
 scratch['no_independent_subject_effect_estimate']=True
 save(D/'SCRATCH_VS_PRIOR_ANALYSIS.json',scratch)
if __name__=='__main__':main()
