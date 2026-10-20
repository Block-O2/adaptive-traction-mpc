from common import *
import collections
rows=load(OUT/'COUNTERFACTUAL_BRANCH_RESULTS.json')['historical_rows'];ranking=load(OUT/'RANKING_FEASIBILITY.json')
by=collections.defaultdict(list)
for r in rows:by[r['snapshot']].append(r)
families={'burden_only':lambda f:f.startswith('velocity_') or f.startswith('acceleration_'),'dose_without_phase_shape':lambda f:f in ['task_duration','actual_excursion','cumulative_angular_travel','phase_or_terminal_endpoint'] ,'burden_and_dose_without_phase_shape':lambda f:f.startswith('velocity_') or f.startswith('acceleration_') or f in ['task_duration','actual_excursion','cumulative_angular_travel','phase_or_terminal_endpoint'],'secondary_only':lambda f:f in ['moment_integral_bound','tracking_bounded_change'],'phase_shape_only':lambda f:f=='phase_progress_q_shape','full_profile':lambda f:True}
records=[]
for profile in ['strict','moderate','wide']:
 for family,predicate in families.items():
  states=[]
  for g,rr in by.items():
   base=next(r for r in rr if max(abs(np.asarray(r['x120'])[58:88]))<1e-8)
   valid=[r for r in rr if not any(predicate(f) for f in r['motion_profiles'][profile]['failed_requirements'])]
   best=min(valid,key=lambda r:r['remaining_J_F_N_s']);states.append(dict(snapshot=g,parent=base['parent'],phase=base['phase'],eligible_count=len(valid),best_id=best['id'],best_source=best['candidate_source'],zero_minus_best_N_s=base['remaining_J_F_N_s']-best['remaining_J_F_N_s']))
  records.append(dict(profile=profile,gate_family=family,eligible_rows=sum(r['eligible_count'] for r in states),force_opportunity_snapshots=sum(r['zero_minus_best_N_s']>.001 for r in states),mean_zero_minus_best_N_s=float(np.mean([r['zero_minus_best_N_s'] for r in states])),states=states,interpretation='Diagnostic component screen using unchanged preregistered tolerances; omitted gates are not relaxed full qualification.'))
ranking['constraint_component_sensitivity']=records
ranking['independence_audit']=dict(exact_snapshot_hashes=13,causal120_state_context_fingerprints_round4=len(set(r['causal_state_fingerprint_round4'] for r in rows)),parent_groups=4,warning='One duplicate causal fingerprint occurs across different source groups. Close RETURN cost equality also indicates limited effective state diversity; hashes/parent names alone do not establish statistical independence.')
save('RANKING_FEASIBILITY.json',ranking)
print('COMPONENTS',[(r['profile'],r['gate_family'],r['eligible_rows'],r['force_opportunity_snapshots'],r['mean_zero_minus_best_N_s']) for r in records],flush=True)
