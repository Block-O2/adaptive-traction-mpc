from common import *
import collections
j=load(OUT/'RANKING_FEASIBILITY.json');rows=load(OUT/'COUNTERFACTUAL_BRANCH_RESULTS.json')['historical_rows']
for p in ['strict','moderate','wide']:
 print('FAILURES',p,collections.Counter(f for r in rows for f in r['motion_profiles'][p]['failed_requirements']))
 for r in rows:
  if r['candidate_source']=='carry':print('CARRY',r['id'],r['motion_profiles'][p])
print('MATCHED',[(s['phase'],len(s['common_exact_plans']),len(s['snapshots']),s['independent_parent_groups'],[(g['parent'],g['regimes']['unconstrained']) for g in s['snapshots']]) for s in j['matched_fixed_candidate_strata']])
print('unique causal states',len(set(r['causal_state_fingerprint_round4'] for r in rows)))
for r in load(OUT/'MOTION_DOSE_HOST_AUDIT.json')['pairs']:
 print('HOST',r['B_id'],'qterminal',r['endpoint_delta_deg'],'travel',r['cumulative_travel_delta_deg'],'profiles', {k:(v['screen_pass'],v['failed_requirements']) for k,v in r['profiles'].items()})
print('max inclusive error',j['uncertainty'])
