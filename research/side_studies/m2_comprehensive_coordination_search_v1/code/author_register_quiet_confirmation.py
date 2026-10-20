from pathlib import Path
import json,time,shutil,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_comprehensive_coordination_search_v1')
assert not any(r['status']=='RUNNING' for r in json.loads((S/'TASK_LEDGER.json').read_text()).values())
rows=[]
for ident,base in [('004_B_quiet_retest_nominal','003_B_confirm_nominal_harness_retry'),('005_B_quiet_retest_deviation','002_B_confirm_deviation')]:
 cfg=json.loads((S/'queue'/(base+'.json')).read_text());cfg.update(id=ident,qualification_group='last_quiet_environment_retest',performance_context='Single physics owner; no simultaneous model benchmarks, source scans, or other task tools until native run joined; original 45s resource monitoring retained')
 p=S/'queue'/(ident+'.json');assert not p.exists();p.write_text(json.dumps(cfg,indent=2)+'\n');rows.append(dict(id=ident,input_sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
out=dict(status='PREREGISTERED',registered_unix=time.time(),reason='Both new full runs preserved physical/safety/causality but missed frozen practical FAST service tails; final two quiet confirmations distinguish repeatable host slowdown from transient disturbance',rows=rows,source_config_control_unchanged=True,all_prior_failures_retained=True,no_threshold_changes=True,stop_if_repeat_fails=True,no_further_B_optimization=True,scope='Tested conditions only, no guarantee over future host resource modes')
(S/'reports/QUIET_RETEST_REGISTRATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
