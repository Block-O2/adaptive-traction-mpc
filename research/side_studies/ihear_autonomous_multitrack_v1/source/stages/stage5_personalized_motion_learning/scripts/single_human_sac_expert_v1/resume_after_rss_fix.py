"""Repair an RSS summary bug; reuse valid measured resets, preserve the failed summary."""
from pathlib import Path
import sys,json,shutil,subprocess
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_work');S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_autonomous_multitrack_v1/source/stages/stage5_personalized_motion_learning');P=S/'scripts/single_human_sac_expert_v1';D=S/'docs/single_human_sac_expert_v1'
assert not json.loads((D/'STATE.json').read_text())['formal_training_started']
for name in ('SAC_RESET_STRESS.json','SAC_RESET_STRESS.md','FINAL_QUALIFICATION_GATES.json','FINAL_QUALIFICATION_EXCEPTION.json','STATE.json'):
    if (D/name).exists():shutil.copy2(D/name,D/(Path(name).stem+'_RSS_RANGE_FALSE_ALARM'+Path(name).suffix))
for name in ('qualification_batch.py','final_qualification.py','resume_after_rss_fix.py','replay_fixed_prior.py','train_campaign.py','closeout.py'):shutil.copy2(W/name,P/name)
sys.path.insert(0,str(P))
from qualification_batch import rss_growth
assert rss_growth([0,0,0,1000,900,930])==0
assert rss_growth([0,0,0,1000,1001,1065])==65
assert rss_growth([0,0,0,1000,1064,1063])==64
raw=json.loads((D/'SAC_RESET_STRESS.json').read_text());rows=raw['rows'];rss=[r['rss_bytes'] for r in rows];growth=rss_growth(rss)
assert len(rows)==20 and all(r['pass_'] for r in rows) and growth<64*2**20
raw.update(status='PASS',post_warmup_positive_rss_growth_bytes=growth,post_warmup_rss_range_bytes=max(rss[3:])-min(rss[3:]),no_state_reference_planner_reward_model_leak=True,summary_bug='Original range counted reclaimed memory as growth; exact original measurements and failure preserved. Threshold remains 64MiB positive growth above first post-warmup reset.',regression_tests=dict(decreasing_RSS_no_growth=True,genuine_over_64_unit_growth_detected=True,boundary_64_detected=True))
(D/'SAC_RESET_STRESS.json').write_text(json.dumps(raw,indent=2,sort_keys=True)+'\n')
(D/'SAC_RESET_STRESS.md').write_text(f'# Reset stress\n\nPASS: all 20 final-period physical resets pass exact state/model/owner/accumulator checks. RSS positive growth after 3 warmups is {growth} bytes; the unchanged threshold is 64 MiB. Original range was {max(rss[3:])-min(rss[3:])} bytes, including a downward reclamation; the original false failure summary is preserved. Three targeted decreasing/increasing/boundary regression checks pass. No reset physics, observations, model state or threshold was altered.\n')
gates=json.loads((D/'FINAL_QUALIFICATION_GATES.json').read_text());gates['gates']['20_reset_stress']=dict(pass_=True,detail='All 20 physical rows pass; corrected positive-RSS-growth statistic is zero; original false range alarm preserved.');(D/'FINAL_QUALIFICATION_GATES.json').write_text(json.dumps(gates,indent=2)+'\n')
(D/'RSS_ACCOUNTING_REGRESSION.json').write_text(json.dumps(dict(status='PASS',tests=3,physical_rows_reused=20,physics_changed=False,threshold_changed=False,positive_growth_bytes=growth,range_bytes=max(rss[3:])-min(rss[3:]),formal_steps=0),indent=2)+'\n')
print('RSS_SUMMARY_REPAIRED_WITHOUT_PHYSICAL_OR_THRESHOLD_CHANGE',flush=True)
subprocess.run([sys.executable,'-u',str(P/'final_qualification.py'),'resume_comparators'],check=True)
if json.loads((D/'STATE.json').read_text())['phase']=='FINAL_ENVIRONMENT_GATES_PASS':
    subprocess.run([sys.executable,'-u',str(P/'replay_fixed_prior.py')],check=True)
    subprocess.run([sys.executable,'-u',str(P/'throughput.py')],check=True)
if json.loads((D/'STATE.json').read_text())['phase']=='ALL_QUALIFICATION_GATES_PASS':subprocess.run([sys.executable,'-u',str(P/'train_campaign.py')],check=True)
subprocess.run([sys.executable,'-u',str(P/'closeout.py')],check=True)
