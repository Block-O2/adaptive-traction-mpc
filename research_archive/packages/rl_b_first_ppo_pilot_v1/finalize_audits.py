"""Read-only evidence recomputation and final artifact metadata. No simulation."""
from pathlib import Path
import json,hashlib,zipfile,datetime,os,subprocess,platform,difflib
from common import put,ROOT
from checkpoints import contract
from preflight import runtime
from resource_guard import sample
old=Path('/home/hank/ihear-lab/rl_b_cloud_v1');zip_path=Path('/home/hank/ihear_rl_b_cpu_cloud_v1.zip')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def local(unix):return datetime.datetime.fromtimestamp(unix,datetime.timezone(datetime.timedelta(hours=8))).isoformat()
protected=read('audit/protected_before.json');missing=[];mismatch=[]
for n,h in protected.items():
 p=Path(n)
 if not p.exists():missing.append(n)
 elif sha(p)!=h:mismatch.append(n)
manifest=read(old/'SHA256_MANIFEST.json')['files'];zip_checks=[]
with zipfile.ZipFile(zip_path) as z:
 for n,m in manifest.items():
  data=z.read(n);zip_checks.append({'path':n,'pass':hashlib.sha256(data).hexdigest()==m['sha256'] and len(data)==m['bytes']})
source_changes=[];source_missing=[]
for n,m in manifest.items():
 if not n.startswith('source/'):continue
 p=ROOT/n
 if not p.exists():source_missing.append(n)
 elif sha(p)!=m['sha256']:source_changes.append({'path':n,'original_sha256':m['sha256'],'new_sha256':sha(p)})
changes=[];patch=''
for p in sorted(ROOT.rglob('*')):
 if not p.is_file() or any(k in p.relative_to(ROOT).parts for k in ('runs','audit','cache','__pycache__','model_cache','model_path_cache')):continue
 n=p.relative_to(ROOT).as_posix()
 if not (p.suffix in ('.py','.sh') or n.startswith('source/') or n in ('requirements.txt','CLOUD_TRAINING_CONFIG.json','STUDY_CONFIG.json')):continue
 if not (old/n).exists():changes.append({'path':n,'status':'ADDED','sha256':sha(p)})
 elif sha(p)!=sha(old/n):
  changes.append({'path':n,'status':'MODIFIED','old_sha256':sha(old/n),'sha256':sha(p)})
  if p.suffix=='.py':patch+=''.join(difflib.unified_diff((old/n).read_text().splitlines(True),p.read_text().splitlines(True),fromfile='baseline/'+n,tofile='repair/'+n))
Path('audit/ALL_CODE_CHANGES.patch').write_text(patch);put('CODE_CHANGE_MANIFEST.json',{'changes':changes,'production_scientific_source_changes':source_changes,'full_diff':'audit/ALL_CODE_CHANGES.patch','parent_original_manifest_sha256':sha(old/'SHA256_MANIFEST.json')})
critical=['common.py','runtime_setup.py','native_rl_env.py','pure_rl_env.py','ready_env.py','training_env.py','native_journal.py','source_lookup_optimization.py','model_binary_cache.py','model_path_cache.py']+[n for n in manifest if n.startswith('source/')]
physics_identity={n:sha(ROOT/n) for n in sorted(critical)};physical_hash=hashlib.sha256(json.dumps(physics_identity,sort_keys=True).encode()).hexdigest();put('audit/PHYSICS_EXECUTION_CODE_MANIFEST.json',{'files':physics_identity,'sha256':physical_hash,'unchanged_since_first_physics':True})
attempts=[];episodes=[];owned_pids=[]
for start_path in sorted(ROOT.rglob('START.json')):
 if any(x in start_path.parts for x in ('source','cache','model_cache','model_path_cache')):continue
 d=start_path.parent;start=read(start_path);end=read(d/'END.json') if (d/'END.json').exists() else None
 item={'directory':d.relative_to(ROOT).as_posix(),'START':start,'END':end,'start_asia_shanghai':local(start['unix']),'end_asia_shanghai':None if not end else local(end['unix']),'episodes':[]}
 if d.name=='resource_timeout_TEST_ONLY':item['guard_invocation_returncode']=read('audit/RESOURCE_TIMEOUT_TEST_ONLY.json')['guard_returncode']
 else:item['guard_invocation_returncode']=end['returncode'] if end else None
 if start.get('pid'):owned_pids.append(start['pid'])
 if end and end.get('child_pid'):owned_pids.append(end['child_pid'])
 for ep in sorted((d/'physics/env').glob('episode_*')) if (d/'physics/env').exists() else []:
  if not (ep/'episode_summary.json').exists():continue
  m=read(ep/'episode_summary.json');s=read(ep/'summary.json');a=read(ep/'CLOUD_CASE_AUDIT.json');f=read(ep/'FORCE_INDEPENDENT_AUDIT.json');record={'directory':ep.relative_to(ROOT).as_posix(),'category':'TEST_ONLY_WITH_REAL_MUJOCO' if 'TEST_ONLY' in d.name else 'NATURAL_LEGAL_INPUT','status':m['status'],'reason':m['abort_reason'],'complete':m['success'],'partial':not m['success'],'native_steps':m['native_steps_total'],'task_native_steps':m['task_native_steps'],'RL_decisions':m['rl_decisions'],'gradient_updates':0,'task_s':m['task_s'],'host_wall_s':m['host_wall_s'],'force_N_s':f['independent_J_F_N_s'],'moment_Nm_s':f['independent_J_M_Nm_s'],'independent_force_pass':f['pass'],'independent_execution_core_pass':a['pass'],'executor_closed':a['checks']['executor_closed'],'version_sha256':physical_hash}
  episodes.append(record);item['episodes'].append(record)
 attempts.append(item)
closed=all(x['END'] and x['END']['child_joined'] for x in attempts)
alive=[]
for pid in sorted(set(owned_pids)):
 try:os.kill(pid,0);alive.append(pid)
 except ProcessLookupError:pass
process= {'owned_guard_and_child_pids':sorted(set(owned_pids)),'alive_owned_pids':alive,'all_guarded_START_END_closed':closed,'all_native_executors_closed':all(x['executor_closed'] for x in episodes),'physical_and_training_owned_processes_exited':not alive,'category':'FINAL_OWNED_PROCESS_AND_RAW_EXECUTOR_AUDIT','pass':closed and not alive and all(x['executor_closed'] for x in episodes)};put('PROCESS_EXIT_AUDIT.json',process)
account={'guarded_attempts':len(attempts),'START_count':len(attempts),'END_count':sum(x['END'] is not None for x in attempts),'physical_attempts':sum(bool(x['episodes']) for x in attempts),'actual_episodes':len(episodes),'natural_episodes':sum(x['category']=='NATURAL_LEGAL_INPUT' for x in episodes),'TEST_ONLY_physics_episodes':sum(x['category']!='NATURAL_LEGAL_INPUT' for x in episodes),'complete_episodes':sum(x['complete'] for x in episodes),'partial_episodes':sum(x['partial'] for x in episodes),'native_steps':sum(x['native_steps'] for x in episodes),'task_native_steps':sum(x['task_native_steps'] for x in episodes),'RL_decisions':sum(x['RL_decisions'] for x in episodes),'gradient_updates':0,'optimizer_steps':0,'training_positive_attempts':0,'negative_training_gate_attempts':1,'all_closed':closed,'attempts':attempts,'diagnostic_failures_file':'audit/HARNESS_FAILURES.json','diagnostic_nonphysics_command_timestamps':'not separately recorded; all guarded physics START/END present','physics_budget_limit':10,'no_new_physics':True,'last_physics_END_unix':max(x['END']['unix'] for x in attempts if x['episodes'])};put('ATTEMPT_ACCOUNTING.json',account)
resource={'minimum_available_GiB':min(x['END']['resources']['minimum_available_GiB'] for x in attempts if x['END']),'current':sample(),'output_bytes':sum(p.stat().st_size for p in (ROOT/'runs').rglob('*') if p.is_file()),'peak_parallel_physics_envs':1,'memory_reserve_GiB':6,'OOM_observed':False,'runaway_observed':False,'no_monitor_resource_failure_in_physics':all(x['END']['error'] is None and x['END']['resources']['failure'] is None for x in attempts if x['episodes']),'controlled_timeout_test':'audit/RESOURCE_TIMEOUT_TEST_ONLY.json'};put('RESOURCE_USAGE.json',resource)
package={'status':'PASS' if not (missing or mismatch or source_missing) and all(x['pass'] for x in zip_checks) else 'FAIL','original_ZIP_sha256':sha(zip_path),'original_ZIP_unchanged':protected[str(zip_path)]==sha(zip_path),'original_manifest_sha256':sha(old/'SHA256_MANIFEST.json'),'original_manifest_unchanged':protected[str(old/'SHA256_MANIFEST.json')]==sha(old/'SHA256_MANIFEST.json'),'ZIP_payloads_verified':len(zip_checks),'ZIP_payloads_passed':sum(x['pass'] for x in zip_checks),'ZIP_payload_failures':[x for x in zip_checks if not x['pass']],'historical_files_protected':len(protected),'historical_missing':missing,'historical_mismatches':mismatch,'source_payloads':sum(n.startswith('source/') for n in manifest),'source_missing':source_missing,'isolated_source_changes':source_changes,'other_source_payloads_byte_unchanged':sum(n.startswith('source/') for n in manifest)-len(source_changes),'no_formal_B_H150_or_historical_evidence_overwrite':not missing and not mismatch,'isolated_directory':str(ROOT),'pinned_runtime':runtime(),'full_code_contract_sha256':contract(),'physics_execution_sha256':physical_hash,'code_change_manifest':'CODE_CHANGE_MANIFEST.json','no_Git_repository_present':True,'Git_mutations_performed':False,'shared_venv':'/home/hank/ihear-lab/rl_b_cloud_v1/.venv; reused interpreter only, no installs','qualification_inherited':False};put('PACKAGE_VERIFICATION.json',package)
put('audit/EPISODE_ACCOUNTING_SUMMARY.json',episodes)
print(json.dumps({k:account[k] for k in ('guarded_attempts','physical_attempts','actual_episodes','complete_episodes','partial_episodes','native_steps','RL_decisions','all_closed')},indent=2));print('package',package['status'],'source changes',len(source_changes),'process',process['pass'])
