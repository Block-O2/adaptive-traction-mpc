from pathlib import Path
import json,os,hashlib,datetime,difflib,zipfile
R=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(R))
from checkpoints import contract,sha
from common import put
required=['REPORT.md','CLOUD_ENVIRONMENT_AUDIT.md','PACKAGE_INTEGRITY_AUDIT.json','G4_PHYSICAL_VALIDATION.json','RL_EXECUTION_VALIDATION.json','PPO_SMOKE_RESULTS.json','CHECKPOINT_RESUME_AUDIT.json','CPU_BENCHMARK_RESULTS.json','RESOURCE_USAGE.json','ATTEMPT_ACCOUNTING.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md']
for n in required:
 p=R/n;assert p.is_file() and p.stat().st_size>0,n
 if p.suffix=='.json':json.loads(p.read_text())
owned_names={'resource_guard.py','run_rollout.py','cloud_g4_cases.py','train.py','evaluate.py','qualify.py','smoke_sequence.py','measure.py','dual_benchmark.py'}
owned=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==os.getpid():continue
 try:
  cwd=(p/'cwd').resolve();argv=(p/'cmdline').read_bytes().split(b'\0');args=[x.decode(errors='replace') for x in argv if x]
  if not cwd.is_relative_to(R):continue
  if len(args)>=2 and 'python' in Path(args[0]).name and Path(args[1]).name in owned_names:
   owned.append({'pid':int(p.name),'cwd':str(cwd),'argv':args})
 except (OSError,ValueError):pass
assert not owned,owned
account=json.loads((R/'ATTEMPT_ACCOUNTING.json').read_text());assert account['START_count']==account['END_count']==12 and account['all_children_joined']
for p in (R/'runs').rglob('START.json'):
 end=json.loads(p.with_name('END.json').read_text());assert end['child_joined'];assert end['resources']['monitor_joined'];assert end['error'] is None
 assert end['returncode']==(1 if p.parent.name=='ppo_gate_negative_01' else 0)
eps=0;native=0;allchecks=[]
for p in (R/'runs').rglob('CLOUD_CASE_AUDIT.json'):
 x=json.loads(p.read_text());m=json.loads(p.with_name('episode_summary.json').read_text());assert x['ownership']['native_steps_all']==m['native_steps_total'];assert x['checks']['single_native_owner_torque_and_source_age'];eps+=1;native+=m['native_steps_total'];allchecks.append({'episode':p.parent.relative_to(R).as_posix(),'executor_closed':x['checks']['executor_closed']})
assert eps==12 and all(x['executor_closed'] for x in allchecks)
assert not list((R/'runs').rglob('*.writing.*'))
assert not list((R/'runs').rglob('checkpoints/*.zip'))
ready=json.loads((R/'READINESS.json').read_text());assert ready['G4_TERMINATION_REWARD_PASS']=='FAIL' and ready['RL_EXECUTION_CONTRACT_PASS']=='FAIL';assert ready['contract_sha256']==contract()
pkg=json.loads((R/'PACKAGE_VERIFICATION.json').read_text());assert pkg['DEPLOYMENT_PASS'] and pkg['active_scientific_source_manifest_matches'] and pkg['original_SHA256_MANIFEST_unchanged'];assert sha('/home/hank/ihear_rl_b_cpu_cloud_v1.zip')=='9ab8622703a84a71501bc7fcd24c665ff0bc2262979cb2857c88e146a2bc638d'
active=json.loads((R/'deployment_audit/DEPLOYED_SOURCE_MANIFEST.json').read_text())
for n,rec in active['files'].items():assert sha(R/n)==rec['sha256'],n
changes=[]
with zipfile.ZipFile('/home/hank/ihear_rl_b_cpu_cloud_v1.zip') as z:
 for item in pkg['documented_deployment_overlay']:
  n=item['path'];a=z.read(n).decode().splitlines(keepends=True);b=(R/n).read_text().splitlines(keepends=True);changes.extend(difflib.unified_diff(a,b,fromfile='uploaded/'+n,tofile='deployed/'+n))
 for p in sorted(R.glob('cloud_*.py')):
  if p.name not in z.namelist():changes.extend(difflib.unified_diff([],p.read_text().splitlines(keepends=True),fromfile='/dev/null',tofile='deployed/'+p.name))
(R/'deployment_audit/DEPLOYMENT_CHANGES.patch').write_text(''.join(changes))
process={'pass':True,'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'owned_training_or_simulation_processes':owned,'guard_START':12,'guard_END':12,'all_children_joined':True,'all_native_executors_closed':allchecks,'physical_episodes':eps,'native_physics_steps':native,'positive_PPO_updates':0,'checkpoint_generations':0,'remaining_owned_jobs':0}
put(R/'PROCESS_EXIT_AUDIT.json',process)
account['owned_process_exit_check']='PROCESS_EXIT_AUDIT.json';account['final_owned_training_simulation_process_count']=0;put(R/'ATTEMPT_ACCOUNTING.json',account)
with (R/'REPORT.md').open('a') as f:f.write('\n最终封存检查：PROCESS_EXIT_AUDIT.json = PASS；owned 训练/仿真进程 0；12/12 START/END 闭合，全部 child 与 native executor 已退出；科学 source/ 与原 manifest 一致，独立部署 overlay 校验通过。完整输出哈希见 OUTPUT_MANIFEST.json。\n')
files={}
for p in R.rglob('*'):
 if not p.is_file() or any(x in p.relative_to(R).parts for x in ('.venv','cache','__pycache__','source')):continue
 if p.name in ('OUTPUT_MANIFEST.json','FINAL_SEAL_RESULT.json','seal_stdout.log','seal_stderr.log'):continue
 files[p.relative_to(R).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
put(R/'OUTPUT_MANIFEST.json',{'schema':'final_cloud_qualification_outputs_v1','files':files,'scope':'root deliverables, runs, model caches and deployment audit; scientific source/ separately sealed; venv represented by installed freeze/runtime','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
for n,rec in files.items():assert sha(R/n)==rec['sha256'],n
assert contract()==ready['contract_sha256']
seal={'pass':True,'required_deliverables':len(required),'output_files_hashed':len(files),'source_manifest_entries_verified':len(active['files']),'output_manifest_sha256':sha(R/'OUTPUT_MANIFEST.json'),'zip_sha256':sha('/home/hank/ihear_rl_b_cpu_cloud_v1.zip'),'process_exit_audit_pass':True,'START':12,'END':12,'physical_episodes':eps,'native_steps':native,'contract_stable_after_reporting':True,'final_state':'STOP'}
put(R/'deployment_audit/FINAL_SEAL_RESULT.json',seal);print(json.dumps(seal,indent=2))
