from pathlib import Path
import sys,json,shutil,hashlib,difflib
sys.dont_write_bytecode=True
S=Path('/home/hank/ihear-lab/constraint_geometry_learning_v4/runtime')
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_jitter_m2_host_v1')
OLD=S.parent/'b_runtime_qualification_decoupling_v1'
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
for p in W.glob('*.py'):shutil.copy2(p,S/'code'/p.name)
for name in ('SHARED_COORDINATION_ACTION_CONTRACT.json','HISTORICAL_K3_DESIGN_REFERENCE.json'):
 shutil.copy2(OLD/'output'/name,S/'output'/name)
p=S/'code/fast_task_ipc.py';original=p.read_text()
assert 'FAST_M2_CONFIG' not in original
new=original.replace(" packet(sock,0,ready)"," if os.environ.get('FAST_M2_CONFIG'):\n  import host_adapter,json\n  host_adapter.warm(json.loads(open(os.environ['FAST_M2_CONFIG']).read()))\n packet(sock,0,ready)",1)
new=new.replace("  result=fast_task_owner.task_with_certificates(payload) if fast else slow_owner.task_with_certificates(payload)","  result=host_adapter.task_with_certificates(payload) if os.environ.get('FAST_M2_CONFIG') else (fast_task_owner.task_with_certificates(payload) if fast else slow_owner.task_with_certificates(payload))",1)
new=new.replace("hold_static_mechanics.prepare_guarded(payload,result['value'])","hold_static_mechanics.prepare_guarded(host_adapter.FINAL_PAYLOAD if os.environ.get('FAST_M2_CONFIG') else payload,result['value'])",1)
new=new.replace("  if self.value.get('hold_static_mechanics'):","  if self.value.get('m2_worker_evidence'):ROWS[-1]['m2_worker_evidence']=self.value['m2_worker_evidence']\n  if self.value.get('hold_static_mechanics'):",1)
(S/'versions/fast_task_ipc_original.py').write_text(original);p.write_text(new)
(S/'reports/M2_TRANSPORT_ADAPTER.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),new.splitlines(True),fromfile='C13/fast_task_ipc.py',tofile='M2/fast_task_ipc.py')))
p=S/'code/run_one.py';original=p.read_text()
needle=" interface=PrefixBInterface(dict(method='M0',prefix=cfg.get('prefix',{}),execution_mode=cfg['execution_mode']))"
assert needle in original
new=original.replace(needle," if cfg.get('host_coordinator'):\n  import host_adapter\n  cfg['durable_config_path']=str(S/'queue'/(ident+'.json'))\n  interface=host_adapter.make_interface(cfg)\n else:\n"+needle)
# Fix the original one-space indent under the new else block.
new=new.replace(" else:\n interface=PrefixBInterface", " else:\n  interface=PrefixBInterface")
(S/'versions/run_one_original.py').write_text(original);p.write_text(new)
(S/'reports/M2_RUNNER_ADAPTER.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),new.splitlines(True),fromfile='C13/run_one.py',tofile='M2/run_one.py')))
save(S/'reports/ADAPTER_REGISTRATION.json',dict(status='REGISTERED_BEFORE_PHYSICS',version='M2_C13_ENVELOPE_v1',strict55_guard_on_ms=19,strict55_guard_off_ms=40,unchanged_native_expiry_ms=100,unchanged_current_state_admission=True,issued_count_unchanged=True,transport_original_sha256=hashlib.sha256((S/'versions/fast_task_ipc_original.py').read_bytes()).hexdigest(),modified_sha256=hashlib.sha256((S/'code/fast_task_ipc.py').read_bytes()).hexdigest()))
base=json.loads((OLD/'queue/004_B_quiet_retest_nominal.json').read_text())
base.update(dependencies=[],performance_context='one physical owner; lean native timing, unchanged45s resource sampling',qualification_group='RESEARCH_HOST_EXPERIMENT',research_profile=False,weights=str(S/'weights/frozen_Q_v1'),weights_sha256='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9',candidate_budget=6,activation_reserve_ms=36,strict55_guard=True,method='M0',host_coordinator=False)
for ident,method,coordinator,guard in [('001_zero_residual_smoke','M0',False,True),('002_M2_guard_on_smoke','M2',True,True),('003_M2_guard_off_smoke','M2',True,False)]:
 cfg={**base,'id':ident,'method':method,'host_coordinator':coordinator,'strict55_guard':guard,'prefix':{}}
 save(S/'queue'/(ident+'.json'),cfg)
print('ASSEMBLED: inputs, versioned transport adapter, runner, smoke configs')
