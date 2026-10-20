from common import *
import collections,shutil
def main():
 ranking=load(OUT/'RANKING_FEASIBILITY.json');ds=load(OUT/'COUNTERFACTUAL_BRANCH_RESULTS.json');rows=ds['historical_rows'];by=collections.defaultdict(list)
 for r in rows:
  r['candidate_pool_class']='HISTORICAL_OFFLINE_G_HEAD' if r['candidate_source'].startswith('G_head_') else 'FROZEN_ORDINARY_K3'
  by[r['snapshot']].append(r)
 ordinary=[]
 for g,rr in by.items():
  a=[r for r in rr if r['candidate_pool_class']=='FROZEN_ORDINARY_K3'];best=min(a,key=lambda r:r['remaining_J_F_N_s']);fixed=min(a,key=lambda r:r['frozen_linear_score_N_s']);base=next(r for r in a if max(abs(np.asarray(r['x120'])[58:88]))<1e-8)
  ordinary.append(dict(snapshot=g,parent=base['parent'],phase=base['phase'],candidate_count=len(a),best_id=best['id'],fixed_id=fixed['id'],regret_N_s=fixed['remaining_J_F_N_s']-best['remaining_J_F_N_s'],zero_minus_best_N_s=base['remaining_J_F_N_s']-best['remaining_J_F_N_s'],G_union_improvement_N_s=best['remaining_J_F_N_s']-min(r['remaining_J_F_N_s'] for r in rr)))
 ranking['ordinary_pool_summary']=dict(eligible_rows=sum(r['candidate_count'] for r in ordinary),snapshots=len(ordinary),positive_force_opportunity_snapshots=sum(r['zero_minus_best_N_s']>.001 for r in ordinary),mean_fixed_regret_N_s=float(np.mean([r['regret_N_s'] for r in ordinary])),max_fixed_regret_N_s=max(r['regret_N_s'] for r in ordinary),mean_zero_minus_best_N_s=float(np.mean([r['zero_minus_best_N_s'] for r in ordinary])),states=ordinary,interpretation='Current ordinary candidate pool only; six frozen historical G-head labels remain in full legacy cohort but are not current ordinary/native M2 candidate coverage. No new G generation/training occurred.')
 ranking['independence_audit'].update(model_hash_count=len(set(r['model_hash'] for r in rows)),model_beta_vector_count=len(set(tuple(r['model_beta']) for r in rows)),registered_parent_source_design='prepare_data.py: zero, +0.12 and -0.12 first OUTBOUND K3 parent-table prefixes, common physical/commissioned setup. Fourth source is exposed nominal M2 exact action replay. Not four independent Humans or calibrated populations.',source_design_path=str(MATRIX/'code/prepare_data.py'),source_design_sha256=sha(MATRIX/'code/prepare_data.py'))
 save('RANKING_FEASIBILITY.json',ranking);save('COUNTERFACTUAL_BRANCH_RESULTS.json',ds)
 old=load(MATRIX/'DIAGNOSTIC_ANALYSIS_v1.json');source=load(MATRIX/'output'/(old['source']+'_RESULT.json'));gate=load(MATRIX/'output/060_v1_committed_attribution_REPLAY_GATE.json');selections=load(MATRIX/'output'/(old['source']+'_SELECTIONS.json'))['rows'];results=[]
 for row in old['rows']:
  ident='v1_committed_attribution_'+row['phase']+'_'+str(row['index'])+'_candidate'+str(row['original_selected_index']);branch=load(MATRIX/'output'/(ident+'_DATA.json'));selection=next(s for s in selections if s['context']['phase']==row['phase'] and s['count_before'][row['phase']]==row['index'])
  assert np.array_equal(branch['table'],selection['applied_plan'])
  rolling=source['metric']['J_F']-branch['child']['start_J_F'];commit=branch['remaining_J_F'];delta=commit-rolling
  assert abs(delta-row['continuation_difference_N_s'])<1e-8
  results.append(dict(phase=row['phase'],issued_index=row['index'],selected_branch=ident,commit_remaining_N_s=commit,archived_rolling_remaining_N_s=rolling,commit_minus_archived_rolling_N_s=delta,initial_table_equal=True,causal_context_equal=row['causal_context_equal'],source_prefix_J_F_N_s=branch['child']['start_J_F'],source_full_J_F_N_s=source['metric']['J_F'],evidence_level='HISTORICAL_SCIENTIFIC_EXACT_TRACE_CAUSAL_REPLAY_DIAGNOSTIC',host_value_status='NOT_EVALUABLE',full_executable_state_identity_with_archived_rolling_source='NOT_PROVEN_BY_SAVED_REPLAY_GATE',counterfactual_rolling_labels_for_other_candidates=0))
 evidence=[MATRIX/'DIAGNOSTIC_ANALYSIS_v1.json',MATRIX/'output/060_v1_committed_attribution_REPLAY_GATE.json',MATRIX/'code/replay_diagnostic.py',MATRIX/'code/analyze_diagnostic.py',MATRIX/'output'/(old['source']+'_RESULT.json')]
 save('HISTORICAL_ROLLING_CONTINUATION_AUDIT.json',dict(results=results,replay_gate=gate,source_mode=source['metric']['physical_audit']['unchanged_evaluator']['execution_mode'],source_seed=source['inputs']['seed'],sources=[dict(path=str(p),sha256=sha(p)) for p in evidence],interpretation='Limited existing diagnostic of different continuation after the original selected plan. Exact complete trace and causal context replay, but not a restorable archived host process/RNG/lifecycle hash. One rolling outcome per state cannot identify candidate ranking under rolling continuation. No new replay was run.'))
 # Preserve mechanical failure from the first verification; its assumed phase
 # count was wrong, and no scientific criterion or cohort is altered to fix it.
 hist=OUT/'derived_history';hist.mkdir(exist_ok=True)
 for filename in ['PACKAGE_VERIFICATION.json','VERIFICATION_LOG.txt']:
  p=OUT/filename;q=hist/('initial_'+filename)
  if p.exists() and not q.exists():shutil.copy2(p,q)
 save('VALIDATION_REPAIR_RECORD.json',dict(scope='Audit verifier expected phase-count correction only',initial_assumed_counts=dict(OUTBOUND=55,RETURN=25),actual_counts=dict(collections.Counter(r['phase'] for r in rows)),repair='derive expected counts from the frozen original DATA cohort, not a guessed literal',cohort_unchanged=True,thresholds_unchanged=True,source_protected=True,initial_failure_preserved=str(hist/'initial_PACKAGE_VERIFICATION.json')))
 print('ORDINARY_POOL',ranking['ordinary_pool_summary']['eligible_rows'],ranking['ordinary_pool_summary']['mean_fixed_regret_N_s'],'ROLLING_DIAGNOSTIC',results,flush=True)
if __name__=='__main__':main()
