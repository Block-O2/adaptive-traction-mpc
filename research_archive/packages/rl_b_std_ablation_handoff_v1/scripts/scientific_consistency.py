"""Saved-evidence consistency audit; no new simulation, policy load, or update."""
from pathlib import Path
import json,math
from research_common import ROOT,RUNTIME,read,atomic,sha,now

def main():
 r=read(ROOT/'STD_ABLATION_RESULTS.json');assert r['status']=='COMPLETE';checks={};ident={x['seed']:x for x in read(ROOT/'audit/CHECKPOINT_IDENTITY.json')['cases']};old=read(ROOT/'configs/STD_PLAN.json');new=read(ROOT/'configs/STD_PLAN_v3.json')
 checks['formal_plan_configs_unchanged_through_prephysics_repairs']=[x for x in old['plans'] if x['split']!='pilot']==[x for x in new['plans'] if x['split']!='pilot']
 checks['all_sealed_configs_match']=all(sha(x['config'])==x['sha256'] for x in new['plans'])
 checks['twenty_four_formal_cases_exact_grid']=len([x for x in r['cases'] if x['split']=='preregistered'])==24 and {(x['seed'],x['arm'],x['rng']) for x in r['cases'] if x['split']=='preregistered'}=={(s,a,n) for s in ident for a in ['A','B'] for n in new['streams']}
 checks['pilot_and_identity_excluded_from_rates']=all(p['arms'][a]['attempts']==6 for p in r['per_parent'] for a in ['A','B'])
 checks['all_integral_scopes_correct']=all((x['integral_scope']=='COMPLETE_TASK')==x['success'] for x in r['cases'])
 checks['no_failed_or_unequal_time_pair_reward_claim']=all((x['JF_difference_B_minus_A'] is not None and x['JM_difference_B_minus_A'] is not None)==(x['A_success'] and x['B_success'] and abs(x['A_task_s']-x['B_task_s'])<1e-7) for x in r['pairs'])
 checks['noise_and_initial_physical_prefix_pairing_proven']=len(r['pairs'])==12 and all(x['divergence']['noise_equal'] and x['divergence']['initial_obs_exact'] and x['divergence']['same_preTASK_physics'] for x in r['pairs'])
 rows=[json.loads(s) for s in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
 checks['each_policy_equals_selected_parent_before_and_after']=all(x['policy_before']==x['policy_after']==ident[x['seed']]['snapshot']['policy'] for x in rows)
 checks['each_Adam_equals_selected_parent']=all(x['frozen_snapshot_before']['optimizer']==x['frozen_snapshot_after']['optimizer']==ident[x['seed']]['snapshot']['optimizer'] for x in rows)
 checks['every_resume_identity_audit_pass']=all(read(Path(x['run']).parent/'RESUME_AUDIT.json')['pass_'] for x in rows)
 checks['all_refusals_classified_without_conflating_reference_regression']=all(sum(p['rejection_classes'].values())==sum(n for k,n in p['outcomes'].items() if k!='ACTIVATED') for x in r['cases'] for p in x['planner_by_phase'].values())
 checks['no_gradient_updates']=sum(x['gradient_updates'] for x in rows)==0 and read(ROOT/'LEDGER.json')['optimizer_steps']==0
 checks['no_model_generations_written']=not list((RUNTIME/'jobs').glob('**/*.zip'))
 checks['source_bundles_and_config_lineage_match']=all(all(sha(Path(read(p)['path'])/name)==h for name,h in read(p)['files'].items()) for p in (ROOT/'jobs').glob('*/SOURCE_IDENTITY.json'))
 checks['clipped_gaussian_moments_quadrature_pass']=read(ROOT/'audit/CLIPPED_GAUSSIAN_MOMENTS.json')['numerical_quadrature_all_pass']
 checks['new_raw_independent_recheck_pass']=read(ROOT/'audit/FINAL_FROZEN_RECHECK.json')['pass_']
 result=dict(time_utc=now(),checks=checks,pass_=all(checks.values()),new_physics=0,Adam=0,limitations=['No training-STD causal claim','No new patient or independent initial-state generalization','No formal G4/live matched/Stage2 qualification','Failed partials never used to claim dose gain'])
 atomic(ROOT/'audit/SCIENTIFIC_CONSISTENCY.json',result);print(json.dumps(result));assert result['pass_']
if __name__=='__main__':main()
