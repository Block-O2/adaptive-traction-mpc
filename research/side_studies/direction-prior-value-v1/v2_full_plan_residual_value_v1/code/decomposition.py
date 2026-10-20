from common import *
import numpy as np,csv
PHASES=('OUTBOUND','HOLD','RETURN')
def trace_metrics(metric,base,start):
 p=Path(metric['trace']);p=p if p.is_absolute() else base/'source'/p
 with np.load(p) as z:
  mask=z['stage']=='TASK';t=z['time_s'][mask];force=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);phase=z['task_phase'][mask];weights=np.maximum(0.,t[1:]-np.maximum(t[:-1],start));parts={k:float(np.sum(force[:-1][phase[:-1]==k]*weights[phase[:-1]==k])) for k in PHASES};dur={k:float(np.sum(weights[phase[:-1]==k])) for k in PHASES}
  q=z['evaluation_only_human_state_rad_rad_s'][mask,:2];ref=z['reference_q_rad'][mask];tracking=np.rad2deg(q-ref)
  prefix=float(np.sum(force[:-1]*(np.maximum(0.,np.minimum(t[1:],start)-t[:-1]))));whole=float(np.sum(force[:-1]*np.diff(t)))
  metadata=dict(path=str(p),sha256=sha(p),physical_end_s=float(t[-1]),TASK_force_integral=whole,metric_integral_error=whole-metric['J_F'],prefix_integral=prefix,F_peak=metric['force_peak'],M_integral=metric['moment_integral'],M_peak=metric['moment_peak'],truth_tracking_RMS_deg=np.sqrt(np.mean(tracking**2,axis=0)).tolist(),truth_tracking_peak_deg=np.max(np.abs(tracking),axis=0).tolist(),clearance=metric['physical_clearance'],phase_durations=metric['phase_durations'],valid=metric['valid'],matched_eligible=metric['matched_eligible'],qualified=metric['valid'] and metric['matched_eligible'],truth_fields_are_diagnostic_only=True)
 return parts,dur,metadata
def main():
 oracle=read(NEW/'ORACLE_GATE.json');states=read(AUDIT/'SCORE_DECOMPOSITION.json')['states'];rows=[];outcomes=[(p,read(p)) for p in (AUDIT/'output').glob('*_OUTCOME.json')];cases=read(AUDIT/'AUDIT_CONTRACT.json')['cases']
 for s in states:
  case=next(c for c in cases if c['state']==s['state']);replay=read(AUDIT/'output'/(s['state']+'_REPLAY_PROOF.json'));start=replay['physical_time']
  for r in s['rows']:
   item=next(x for x in case['candidates'] if x['identity']==r['identity']);segments=r['model_segments'];model={k:sum(e['force_cost'] for e in segments if e['phase']==k) for k in PHASES};modeltime={k:sum(e['end_task_s']-e['start_task_s'] for e in segments if e['phase']==k) for k in PHASES};assert abs(sum(model.values())-r['P_score'])<1e-7
   actual={};refs={};metas={};times={}
   for contract,mode in (('COMMITTED','COMMITTED'),('ROLLING_P','P_RECEDING')):
    if mode=='COMMITTED' and item['committed_source']:source=Path(item['committed_source']);record=read(source);base=OLD
    else:source,record=next((p,d) for p,d in outcomes if d['child']['item']['identity']==r['identity'] and d['child']['mode']==mode);base=AUDIT
    actual[contract],times[contract],metas[contract]=trace_metrics(record['metric'],base,start);refs[contract]=dict(outcome=str(source),outcome_sha256=sha(source))
    assert abs(sum(actual[contract].values())-r['mode_costs'][mode])<1e-6
    assert abs(metas[contract]['prefix_integral']-replay['prefix_J_F'])<1e-6
   residual={c:{k:actual[c][k]-model[k] for k in PHASES} for c in actual};continuation={k:actual['ROLLING_P'][k]-actual['COMMITTED'][k] for k in PHASES}
   for k in PHASES:assert abs(residual['ROLLING_P'][k]-residual['COMMITTED'][k]-continuation[k])<1e-7
   rows.append(dict(state=s['state'],identity=r['identity'],index=r['index'],parent_hash=replay['snapshot']['audit_hash'],plan_hash=digest(r['plan']),screening_accepted=r['screening_accepted'],J_model_full=r['P_score'],J_actual={c:sum(parts.values()) for c,parts in actual.items()},DeltaJ_full={c:sum(parts.values()) for c,parts in residual.items()},model_force_cost_by_phase=model,actual_force_cost_by_phase=actual,residual_by_phase=residual,rolling_minus_committed_by_phase=continuation,model_remaining_phase_duration_s=modeltime,actual_remaining_phase_duration_s=times,model_minus_actual_phase_duration_s={c:{k:modeltime[k]-times[c][k] for k in PHASES} for c in actual},model_schedule_segments=segments,metric_metadata=metas,sources=refs,integration='left endpoint physical force norm * exact trace interval; partial first interval clipped at saved fork; inherited prefix excluded',reference_scheduler_interpretation='phase timing and internal model schedule logs retained; request/bridge/tracking/contact approximation and policy replacement are coupled; no invented additive force-error vs timing causal allocation'))
 scales={}
 for contract in ('COMMITTED','ROLLING_P'):
  values=np.array([r['DeltaJ_full'][contract] for r in rows]);ranges={s['state']:float(np.ptp([r['DeltaJ_full'][contract] for r in rows if r['state']==s['state']])) for s in states};means={s['state']:float(np.mean([r['DeltaJ_full'][contract] for r in rows if r['state']==s['state']])) for s in states}
  centered=np.array([r['DeltaJ_full'][contract]-means[r['state']] for r in rows]);scales[contract]=dict(min_median_max_Ns=[float(values.min()),float(np.median(values)),float(values.max())],pooled_RMS_Ns=float(np.sqrt(np.mean(values**2))),within_parent_residual_range_Ns=ranges,parent_mean_residual_Ns=means,within_parent_centered_RMS_Ns=float(np.sqrt(np.mean(centered**2))),interpretation='within-state variation documents candidate/plan dependence; parent means document state/continuation variation; not independent Human/generalization data')
 save(NEW/'FULL_PLAN_ERROR_DECOMPOSITION.json',dict(rows=rows,summary=scales,definition='ROLLING_P residual = committed model error + frozen P continuation effect, both phase-wise and full-task; actual force norm only in offline truth fields',new_high_fidelity=0))
 flat=[]
 for r in rows:
  for c in ('COMMITTED','ROLLING_P'):
   flat.append(dict(state=r['state'],identity=r['identity'],contract=c,parent_hash=r['parent_hash'],plan_hash=r['plan_hash'],accepted=r['screening_accepted'],model=r['J_model_full'],actual=r['J_actual'][c],residual=r['DeltaJ_full'][c],**{k+'_residual':r['residual_by_phase'][c][k] for k in PHASES}))
 with (NEW/'ORACLE_CANDIDATE_DIAGNOSTICS.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
 print(json.dumps(dict(rows=len(rows),summary=scales)))
if __name__=='__main__':main()
