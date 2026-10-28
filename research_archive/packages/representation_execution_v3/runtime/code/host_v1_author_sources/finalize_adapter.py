from pathlib import Path
import json,time,hashlib,shutil,difflib
S=Path('/home/hank/ihear-lab/representation_execution_v3/runtime')
before=(S/'versions/host_adapter_v1_failed.py').read_text();after=(S/'code/host_adapter.py').read_text()
(S/'reports/ADAPTER_REPAIR.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='adapter_v1_failed',tofile='adapter_v2_final')))
r=json.loads((S/'reports/ADAPTER_REPAIR.json').read_text());r.update(status='OFFLINE_VALIDATED',cause='commissioning_owner compiles _run_executed_case in a copied globals dictionary before Async snapshot installation; actual loop kept old snapshot and sent tuple2. Partial repair v2a passed raw packets to C13 but left pending hint; failed004 preserved',failed_attempts=['002_M2_guard_on_smoke','003_M2_guard_off_smoke','004_M2_guard_on_retry'],intermediate_patch_versions=['v2a_native_raw_pass_through','v2b_bind_actual_compiled_snapshot_namespace'],repair_cycle_count=1,patch_revision_count=2,limit='No further M2 adapter repair if final route fails',change='Bind actual cloned runtime snapshot namespace, retaining original multirate wrapper; fail-closed envelope hash and source timestamp checks; original tuple routing retained',after_sha256=hashlib.sha256(after.encode()).hexdigest(),validated_unix=time.time())
(S/'reports/ADAPTER_REPAIR.json').write_text(json.dumps(r,indent=2)+'\n')
for old,new,guard in [('005_M2_guard_off_retry','005_M2_guard_off_retry',False),('004_M2_guard_on_retry','016_M2_guard_on_final',True)]:
 cfg=json.loads((S/'queue'/(old+'.json')).read_text());cfg.update(id=new,strict55_guard=guard,adapter_version='M2_C13_ENVELOPE_v2_final')
 if new==old:shutil.copy2(S/'queue'/(old+'.json'),S/'versions'/(old+'_unrun_config_v2a.json'))
 (S/'queue'/(new+'.json')).write_text(json.dumps(cfg,indent=2)+'\n')
print('Final adapter route frozen; no additional repair cycle allowed')
