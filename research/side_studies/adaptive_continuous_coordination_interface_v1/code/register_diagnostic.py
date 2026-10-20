from pathlib import Path
import shutil,json,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_interface_v1')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1')
ident='009_isolated_B_compiled_FAST_diagnostic'
assert ident not in json.loads((S/'TASK_LEDGER.json').read_text())
assert len(json.loads((S/'TASK_LEDGER.json').read_text()))==8
shutil.copy2(W/'compiled_fast_diagnostic.py',S/'code/compiled_fast_diagnostic.py')
cfg=json.loads((S/'queue/007_deviation_P2_seed2_B.json').read_text());cfg.update(id=ident,entry='compiled_fast_diagnostic.py',qualification_group='ISOLATED_ATTRIBUTION_NOT_PAIRED',pair_id=None,attribution=True,low_overhead_diagnostic=False)
registration=dict(status='PASS',registered_unix=time.time(),id=ident,additional_attempts=1,reason='Two actual B rolling1s FAIL; preserve unchanged numerical6ms gate and capture wall/threadCPU/Linux runqueue wait on verified actual compiled binding. No instrumented run enters matched pairs.',source_sha256=hashlib.sha256((S/'code/compiled_fast_diagnostic.py').read_bytes()).hexdigest(),same_frozen_B=True,Q_updates=0,config=cfg,primary_pairs_immutable=True,no_repeat_policy='Single diagnostic attempt only, regardless of recurrence or observed result')
(S/'reports/ISOLATED_FAST_DIAGNOSTIC_REGISTRATION.json').write_text(json.dumps(registration,indent=2)+'\n')
(S/'queue'/(ident+'.json')).write_text(json.dumps(cfg,indent=2)+'\n')
print(json.dumps(dict(status='PASS',id=ident,registered_unix=registration['registered_unix'])))
