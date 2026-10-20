from task_bootstrap import *
import numpy as np
from causal_timing_report import quantile
def main():
 groups=[]
 for p in sorted((STUDY/'output').glob('18*_RESULT.json'))+sorted((STUDY/'output').glob('19*_RESULT.json')):
  r=json.loads(p.read_text());cfg=r['inputs']
  if 'tradeoff_group' not in cfg:continue
  group=cfg['tradeoff_group'];bucket=next((g for g in groups if g['group']==group),None)
  if bucket is None:bucket=dict(group=group,prefix=cfg['prefix'],seed=cfg['seed'],runs=[]);groups.append(bucket)
  sp=STUDY/'output'/(r['id']+'_SELECTIONS.json');sels=json.loads(sp.read_text()).get('rows',[]) if sp.exists() else [];metric=r['metric'];bucket['runs'].append(dict(id=r['id'],method=cfg['method'],candidate_budget=0 if cfg['method']=='M0' else cfg['candidate_budget'],valid=metric['valid'],J_F=metric['J_F'],force_peak=metric['force_peak'],moment_integral=metric['moment_integral'],moment_peak=metric['moment_peak'],phase_durations=metric['phase_durations'],clearance=metric['clearance'],physical_clearance=metric['physical_clearance'],coordinator_shadow_ms=quantile([s['end_to_end_s']*1000 for s in sels]),fast_prefix_with_SCI_mechanics_shadow_ms=quantile([s.get('fast_coordinator_s',s['end_to_end_s'])*1000 for s in sels]),candidate_count_distribution={str(n):sum(s['candidate_count']==n for s in sels) for n in set(s['candidate_count'] for s in sels)},learning_selection_changes=sum(s.get('plan_changed',False) for s in sels)))
 for group in groups:
  b=next(r for r in group['runs'] if r['candidate_budget']==0)
  for r in group['runs']:r['paired_force_reduction_percent']=100*(b['J_F']-r['J_F'])/b['J_F'];r['paired_moment_increase_percent']=100*(r['moment_integral']-b['moment_integral'])/b['moment_integral']
 aggregate={}
 for budget in (6,4,2):
  pairs=[(next(r for r in g['runs'] if r['candidate_budget']==0),next(r for r in g['runs'] if r['candidate_budget']==budget)) for g in groups]
  aggregate[str(budget)]=dict(B_mean_J_F=float(np.mean([b['J_F'] for b,m in pairs])),M2_mean_J_F=float(np.mean([m['J_F'] for b,m in pairs])),mean_paired_reduction_percent=float(np.mean([m['paired_force_reduction_percent'] for b,m in pairs])),pooled_force_reduction_percent=100*(sum(b['J_F'] for b,m in pairs)-sum(m['J_F'] for b,m in pairs))/sum(b['J_F'] for b,m in pairs),mean_paired_moment_increase_percent=float(np.mean([m['paired_moment_increase_percent'] for b,m in pairs])),nominal_mean_paired_reduction_percent=float(np.mean([next(r for r in g['runs'] if r['candidate_budget']==budget)['paired_force_reduction_percent'] for g in groups if g['group'].startswith('nominal')])),deviation_mean_paired_reduction_percent=float(np.mean([next(r for r in g['runs'] if r['candidate_budget']==budget)['paired_force_reduction_percent'] for g in groups if g['group'].startswith('deviation')])),all_valid=all(m['valid'] and b['valid'] for b,m in pairs))
 out=dict(status='SCI_EXPLORATORY_VALID_HOST_NOT_QUALIFIED',groups=groups,aggregate=aggregate,physics_attempts=16,scope='Exposed nominal Human; two independent search seeds plus two preregistered legal prefix states. B nominal trajectory is deterministic and is intentionally shared paired denominator, not independent-Human evidence.',classification='6 is frozen scientific reference; 4/2 are compute-performance tradeoff, not exact equivalence.',host_case='All six actual6/4/2 attempts failed before TASK; budget-dependent actual coordinator latency/late rates are censored, not zero.',timing_caution='SCI full-validation shadow and mechanics scalar shadow remain. Even fast prefix is not a measured deployment latency. Actual worker benchmark reported separately.',adaptation_training=False,phase_C_qualification=False)
 save(STUDY/'reports/SCIENTIFIC_CANDIDATE_TRADEOFF_SUMMARY.json',out);print(json.dumps(dict(status=out['status'],aggregate=aggregate)))
if __name__=='__main__':main()
