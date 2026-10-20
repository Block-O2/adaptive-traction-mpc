"""Freeze finite-budget matched and native references with explicit objective scope."""
import argparse,csv,json
from collections import Counter
from datetime import datetime,timezone
from research_campaign import D,RAW,RUNS,OLD,C,save,summarize_reference
from native_objective_extension import native_sources,summarize
from confirm_references import normalize_descriptor
from audit_all_prior_references import main as audit_prior

def main(intermediate_native=False):
 summarize_reference();sources=native_sources();summarize(sources)
 matched=json.loads((D/'BEST_KNOWN_REFERENCE_TABLE.json').read_text())
 native=json.loads((D/'NATIVE_BEST_KNOWN_REFERENCE_TABLE.json').read_text())
 audit_prior()
 audit=json.loads((D/'ALL_PRIOR_VALID_REFERENCE_AUDIT.json').read_text())
 for row in matched['rows']:
  old=next(r['MATCHED'] for r in audit['rows'] if r['condition']==row['condition'])
  row['previous_timing_isolated_best_J_F_n_s']=row['previous_best_J_F_n_s']
  row['previous_best_J_F_n_s']=old['J_F_task_n_s']
  row['previous_best_scope']='ALL prior VALID matched paths, including timing-confounded paths'
  row['previous_all_valid_best_run_id']=old['run_id']
  for level in row['best_vs_level']:row['best_vs_level'][level]=min(row['best_vs_level'][level],old['J_F_task_n_s'])
  if old['J_F_task_n_s']<row['best_known_J_F_n_s']:
   baseline=json.loads((OLD/f'matched_baseline_{row["condition"]}_certified/rollout_result.json').read_text())
   record=json.loads((OLD/old['run_id']/'rollout_result.json').read_text())
   residual={p:record[p.lower()+'_duration_s']-baseline[p.lower()+'_duration_s'] for p in ('OUTBOUND','RETURN')}
   same_count=all(len(record['planned_segments'][p])==len(baseline['planned_segments'][p]) for p in ('OUTBOUND','RETURN'))
   row.update(best_known_J_F_n_s=old['J_F_task_n_s'],best_source='previous_all_valid_reference',
    best_run_id=old['run_id'],best_parameters=normalize_descriptor(old['pattern']),
    best_duration_s=record['duration_s'],phase_timing_residual_s=residual,
    timing_isolated=same_count and max(abs(x) for x in residual.values())<=.025+1e-9)
  row['improvement_over_previous_n_s']=row['previous_best_J_F_n_s']-row['best_known_J_F_n_s']
  row['benefit_n_s']=row['baseline_J_F_n_s']-row['best_known_J_F_n_s']
 curve_path=D/'REFERENCE_SEARCH_CONVERGENCE.json'
 archived_curve=RAW/'reference_curve_before_all_prior_audit.json'
 if not archived_curve.exists():archived_curve.write_bytes(curve_path.read_bytes())
 adjusted_curve=json.loads(curve_path.read_text())
 for row in matched['rows']:
  best=row['previous_best_J_F_n_s']
  for point in adjusted_curve:
   if point['condition']!=row['condition']:continue
   if point['status']=='VALID':best=min(best,point['candidate_J_F_n_s'])
   point['best_known_J_F_n_s']=best
 save(curve_path,adjusted_curve)
 with (D/'REFERENCE_SEARCH_CONVERGENCE.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(adjusted_curve[0]));writer.writeheader();writer.writerows(adjusted_curve)
 for discovery_file in ('VALUE_SELECTED_REFERENCE_DISCOVERIES.json','POST_PILOT_PROBE_REFERENCE_DISCOVERIES.json'):
  discoveries_path=D/discovery_file
  if not discoveries_path.exists():continue
  for discovery in json.loads(discoveries_path.read_text())['rows']:
   if not discovery['independent_confirmation_pass']:continue
   row=next(r for r in matched['rows'] if r['condition']==discovery['condition'])
   row.setdefault('confirmed_non_cem_value_discoveries',[]).append(discovery)
   if discovery['J_F_task_n_s']>=row['best_known_J_F_n_s']:continue
   row.setdefault('cem_search_only_best_J_F_n_s',row['best_known_J_F_n_s'])
   baseline=json.loads((OLD/f'matched_baseline_{row["condition"]}_certified/rollout_result.json').read_text())
   record=json.loads((RUNS/discovery['confirmation_run_id']/'rollout_result.json').read_text())
   residual={p:record[p.lower()+'_duration_s']-baseline[p.lower()+'_duration_s'] for p in ('OUTBOUND','RETURN')}
   same_count=all(len(record['planned_segments'][p])==len(baseline['planned_segments'][p]) for p in ('OUTBOUND','RETURN'))
   row.update(best_known_J_F_n_s=discovery['J_F_task_n_s'],best_source='confirmed_post_pilot_probe' if discovery_file.startswith('POST_') else 'confirmed_offline_value_selection',
    best_run_id=discovery['confirmation_run_id'],best_parameters=discovery['descriptor'],
    benefit_n_s=row['baseline_J_F_n_s']-discovery['J_F_task_n_s'],
    improvement_over_previous_n_s=row['previous_best_J_F_n_s']-discovery['J_F_task_n_s'],
    best_duration_s=record['duration_s'],phase_timing_residual_s=residual,
    timing_isolated=same_count and max(abs(x) for x in residual.values())<=.025+1e-9)
   # Complexity/search curves retain their CEM-only envelope; this extra
   # confirmed Q-selected path is labelled separately instead of laundering
   # it into a CEM iteration or claiming additional control-point freedom.
   row['best_vs_level_scope']='CEM-only nested envelope; separately confirmed value-selected reference recorded above'
 attempts=[]
 for path in sorted((RAW/'search_proposals').glob('*.json')):
  entry=json.loads(path.read_text());rp=RUNS/entry['run_id']/'rollout_result.json'
  if not rp.exists():continue
  result=json.loads(rp.read_text())
  if result['status']=='RUNNING':continue
  attempts.append({**entry,'status':result['status'],'J_F_n_s':result.get('J_F_task_n_s')})
 for row in matched['rows']:
  row['reference_scope']='conditional matched scheduling, not unrestricted primary objective'
  row['level_evaluations']={str(l):sum(a['condition']==row['condition'] and a['level']==l for a in attempts) for l in (1,2,3)}
  row['restart_generation_evaluations']={f'L{l}_R{r}_G{g}':sum(a['condition']==row['condition'] and a['level']==l and a['restart']==r and a['generation']==g for a in attempts)
   for l in (1,2,3) for r in (0,1) for g in (0,1,2)}
  row['incomplete_levels_cannot_establish_plateau']=[l for l in (1,2,3) if row['level_evaluations'][str(l)]<2*3*8]
 native['status']='RUNNING' if intermediate_native else 'COMPLETE_FINITE_BUDGET_SEARCH';native['not_global_optimum']=True
 for row in native['rows']:
  row['reference_scope']='absolute measured cuff-force integral; native timing may change'
  row['timing_isolated_claim']=False
 matched.update(status='COMPLETE_FINITE_BUDGET_SEARCH',not_global_optimum=True,
  primary_objective_rows=native['rows'],
  scope='rows are conditional matched-duration references; primary_objective_rows are native-scheduler absolute references',
  current_learning_scope='matched-only fitted models and pilot; native data excluded from fitting')
 save(D/'BEST_KNOWN_REFERENCE_TABLE.json',matched);save(D/'NATIVE_BEST_KNOWN_REFERENCE_TABLE.json',native)
 primary=[]
 for m,n in zip(matched['rows'],native['rows']):
  assert m['condition']==n['condition']
  primary.append({**n,'matched_conditional_best_J_F_n_s':m['best_known_J_F_n_s'],
   'absolute_best_reference_scope':'NATIVE_SCHEDULER' if n['best_known_J_F_n_s']<=m['best_known_J_F_n_s'] else 'MATCHED_SCHEDULER',
   'absolute_best_known_J_F_n_s':min(n['best_known_J_F_n_s'],m['best_known_J_F_n_s']),
   'matched_pilot_does_not_automatically_capture_absolute_benefit':True})
 save(D/'ABSOLUTE_PRIMARY_REFERENCE_TABLE.json',{'status':'PROVISIONAL_NATIVE_SEARCH_RUNNING' if intermediate_native else 'COMPLETE','rows':primary,'no_global_optimality':True})
 curve=[]
 for filename,scope in [('REFERENCE_SEARCH_CONVERGENCE.json','MATCHED_CONDITIONAL'),('NATIVE_REFERENCE_SEARCH_CONVERGENCE.json','NATIVE_PRIMARY')]:
  for row in json.loads((D/filename).read_text()):curve.append({**row,'scope':scope})
 save(D/'ALL_REFERENCE_SEARCH_CONVERGENCE.json',curve)
 keys=sorted(set(k for row in curve for k in row))
 with (D/'ALL_REFERENCE_SEARCH_CONVERGENCE.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader();writer.writerows(curve)
 text=['# Best-known reference search','',
  'Absolute matched previous/best costs include ALL prior VALID matched paths, including timing-confounded paths. The previously highlighted timing-isolated reference is retained separately. This prevents claiming improvement over an artificially restricted prior best.','',
  'Primary objective is completed-task measured cuff-force integral with hard safety validity. Native and matched scheduling have different achievable costs. The matched learner study is conditional; its reference is never an unrestricted performance limit.','',
  '|Condition|Matched previous|Matched best|Native previous|Native best|Matched evals|Native evals|',
  '|---|---:|---:|---:|---:|---:|---:|']
 for m,n in zip(matched['rows'],native['rows']):text.append(f'|{m["condition"]}|{m["previous_best_J_F_n_s"]:.6f}|{m["best_known_J_F_n_s"]:.6f}|{n["previous_best_J_F_n_s"]:.6f}|{n["best_known_J_F_n_s"]:.6f}|{m["evaluations"]}|{n["evaluations"]}|')
 text+=['','Units N·s. Level-wise envelopes retain earlier levels and prior references; an unchanged envelope with sparse/missing evaluations is not a plateau. Restart results, feasibility, completed generation counts, phase timing residuals and descriptors are in the JSON tables.','',
  'Directed CEM evaluates real frozen Scientific Simulation. Every rejection remains recorded. Population/restart and finite wall-time budgets limit coverage; no lower bound or global-optimality evidence is claimed. Level 4 was not exercised in this bounded campaign. Separately independently confirmed offline-Q-selected paths can update the best-known table; they are labelled as non-CEM discoveries and do not change the CEM-only convergence/complexity curves.','',
  'New winning paths are independently re-executed from their exact frozen discovery starting state. Deterministic agreement does not establish Human-subject generalization. Native cost changes are not called timing-isolated coordination gains.']
 (D/'BEST_KNOWN_REFERENCE_SEARCH.md').write_text('\n'.join(text)+'\n')
 save(D/'REFERENCE_SEARCH_FINALIZATION.json',{'status':'MATCHED_FINAL_NATIVE_RUNNING' if intermediate_native else 'COMPLETE','timestamp_utc':datetime.now(timezone.utc).isoformat(),
  'matched_completed_evaluations':sum(r['evaluations'] for r in matched['rows']),
  'native_completed_evaluations':native['evaluations'],'all_proposals_real_scientific_evaluations':True,
  'finite_budget_not_optimality':True,'no_level4_claim':True})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--intermediate-native',action='store_true');a=p.parse_args();main(a.intermediate_native)
