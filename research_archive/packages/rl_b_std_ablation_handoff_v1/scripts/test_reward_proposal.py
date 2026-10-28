"""Replay R4 arithmetic on saved causal measurements; no policy, physics or gradient."""
from pathlib import Path
import importlib.util,json,math
from research_common import ROOT,atomic,read,now,sha
H=ROOT.parent/'rl_b_autonomous_stability_reward_v1';source=ROOT/'unattended/template/scripts/rewards.py';spec=importlib.util.spec_from_file_location('future_rewards_only',source);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
rows=read(H/'FROZEN_EVALUATION_RESULTS.json')['evaluations'];cases=[]
for row in rows:
 ts=read(Path(row['run'])/'RESEARCH_TRANSITIONS.json');total=0.
 for t in ts:
  reward,_=mod.transition('R4',t['reward_before'],t['reward_after'],t['terminal'],t['success'],t['baseline_reward']);total+=reward
 c=mod.VERSIONS['R4'];end=ts[-1]['reward_after'];cost=.0005*end['force']+.020*end['moment']+.02*end['variation'];phi0=ts[0]['reward_before']['phi'];expected=2*((end['phi'] if ts[-1]['success'] else 0)-phi0)+(20-cost if ts[-1]['success'] else -15-max(15,cost))
 cases.append(dict(job=row['job_id'],success=row['success'],sum_matches=abs(total-expected)<1e-7,failed_negative=row['success'] or total<0.,total_replayed=total,scope='arithmetic only; not observed R4 training return'))
zero=dict(phi=0.,force=0.,moment=0.,variation=0.);one=dict(zero,phi=1.)
r0,_=mod.transition('R4',zero,one,False,False,0);r1,_=mod.transition('R4',one,zero,False,False,0);failed,_=mod.transition('R4',zero,zero,True,False,0)
checks=dict(all_52_saved_replays_match=len(cases)==52 and all(x['sum_matches'] for x in cases),all_failed_totals_negative=all(x['failed_negative'] for x in cases),progress_cycle_zero=abs(r0+r1)<1e-12,no_executed_progress_early_failure_negative=failed==-30.,only_declared_moment_price_diff=all(mod.VERSIONS['R4'][k]==mod.VERSIONS['R1'][k] for k in ['progress','complete','failure','force_per_Ns','variation','failure_floor']))
result=dict(time_utc=now(),source_sha256=sha(source),checks=checks,cases=cases,pass_=all(checks.values()),new_physics=0,Adam=0,scope='Reward arithmetic and saved-causal-measurement feasibility only; no performance evidence for R4')
atomic(ROOT/'audit/R4_PROPOSAL_MATH_TESTS.json',result);print(json.dumps(dict(checks=checks,pass_=result['pass_'])));assert result['pass_']
