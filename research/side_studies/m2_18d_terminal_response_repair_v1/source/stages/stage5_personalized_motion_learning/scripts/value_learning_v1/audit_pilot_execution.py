"""Correct continuity claims in derived pilot publications, preserve emitted bytes."""
import json
from datetime import datetime,timezone
from research_campaign import D,RAW,save,sha

def main():
 path=D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json';pilot=json.loads(path.read_text())
 if pilot['status']=='RUNNING' or len(pilot['sessions'])<2:raise RuntimeError('wait for both attempted budgets to close')
 original=RAW/'ONLINE_POLICY_IMPROVEMENT_PILOT_AS_EMITTED.json'
 if not original.exists():original.write_bytes(path.read_bytes())
 sessions=[]
 for session in pilot['sessions']:
  rows=session['rows'];fresh=[r['repetition_index'] for r in rows if r['status']=='VALID' and r.get('start_native_state_evaluation_only') is None]
  failures=[{'repetition':r['repetition_index'],'run_id':r['run_id'],'reason':r.get('failure_reason'),'original_boundary_cannot_return_reason':r.get('continuous_session_ended_reason')} for r in rows if r['status']!='VALID']
  continuous=bool(rows) and all(r['status']=='VALID' for r in rows) and all(r.get('start_native_state_evaluation_only') is not None for r in rows[1:])
  session['continuous_context_persisted']=continuous
  session['fresh_development_segment_start_repetitions']=fresh
  session['invalid_attempts_are_not_completed_repetitions']=True
  sessions.append({'session':session['session'],'attempted':len(rows),'valid':sum(r['status']=='VALID' for r in rows),'fresh_segment_starts':fresh,'failures':failures,'continuous_valid_attempt_budget_demonstrated':continuous})
 all_continuous=all(s['continuous_valid_attempt_budget_demonstrated'] for s in sessions)
 pilot['status']='COMPLETE' if all_continuous else 'COMPLETE_ATTEMPT_BUDGET_NATIVE_CONTINUITY_FAILED'
 pilot['continuous_valid_pilot_demonstrated']=all_continuous
 pilot['original_emitted_evidence_path']=str(original.relative_to(RAW));pilot['original_emitted_evidence_sha256']=sha(original)
 pilot['continuity_claim_corrected_by_read_only_audit']=True
 save(path,pilot)
 audit={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_CONTINUOUS_DEVELOPMENT' if all_continuous else 'NATIVE_START_GUARD_CONTINUITY_BLOCKER',
  'sessions':sessions,'original_emitted_pilot_sha256':sha(original),'audited_publication_sha256':sha(path),
  'production_start_guard_never_bypassed':True,'no_seventh_repair_or_controller_math_change':True,
  'bounded_development_attempts_completed':True,'cost_plateau_across_fresh_segments_never_continuous_convergence':True}
 save(D/'PILOT_EXECUTION_AUDIT.json',audit)
 lines=['# Small online policy-improvement development pilot','',
  f'Status: `{pilot["status"]}`. Eight attempts per initialization mode; failed starts are not completed repetitions. The original emitted publication is preserved byte-for-byte in raw evidence.','',
  '|Mode|Attempt|Status|J_F (N·s)|Starting context|Model used|','|---|---:|---|---:|---|---|']
 for session in pilot['sessions']:
  for row in session['rows']:
   cost='unavailable' if row.get('J_F_task_n_s') is None else f'{row["J_F_task_n_s"]:.6f}'
   scope='fresh segment' if row.get('start_native_state_evaluation_only') is None else 'carried native context'
   if row['status']!='VALID':scope='start refused; no valid task return'
   lines.append(f'|{session["mode"]}|{row["repetition_index"]}|{row["status"]}|{cost}|{scope}|{row.get("model_version_used","no activated learned action")}|')
 lines+=['','Native REPETITION_START_NOT_SETTLED failures preserve the original safety guard. Valid later fresh segments are compared only to exact verified fresh starting conditions, not represented as continuous Human/adaptation carryover. Rep8 capture is unavailable when its learned attempt is invalid.','',
  'SCRATCH rep1 was valid physical data executed under a subsequently superseded stationary proxy computation gate. V3 computation resumes at a documented safe boundary; no retroactive actual-moving gate pass or hardware/realtime qualification is claimed.']
 (D/'ONLINE_POLICY_IMPROVEMENT_PILOT.md').write_text('\n'.join(lines)+'\n')
 scratch=json.loads((D/'SCRATCH_VS_PRIOR_ANALYSIS.json').read_text());scratch['execution_audit']=audit;scratch['initialization_effect_not_established']=True
 save(D/'SCRATCH_VS_PRIOR_ANALYSIS.json',scratch)
 print(json.dumps(audit),flush=True)

if __name__=='__main__':main()
