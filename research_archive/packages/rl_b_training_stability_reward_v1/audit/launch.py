"""Audited v2 launcher derived from the official interface; original inspect retained."""
from pathlib import Path
import os,sys,json,argparse,hashlib,shutil,datetime,subprocess,importlib.util,time
R=Path('/home/hank/ihear-lab/rl_b_std_ablation_handoff_v1');S=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('official_launcher',R/'unattended/next_launch.py');official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)
sha=official.sha;put=official.put
PYTHON=official.PYTHON

def inspect():
 plan,manifest=official.inspect()  # Original template, runtime, all parent hashes and hard limits.
 identity=json.loads((S/'ISOLATED_TEMPLATE_IDENTITY.json').read_text())
 assert sha(R/'unattended/next_launch.py')==identity['official_launcher_sha256'],'OFFICIAL_LAUNCHER_CHANGED'
 for name,h in identity['files'].items():assert sha(S/name)==h,'ISOLATED_SOURCE_CHANGED:'+name
 pre=json.loads((S/'audit/PREFLIGHT.json').read_text());assert pre['pass_'] and pre['native_steps']==pre['optimizer_updates']==0
 assert sha(R/'OUTPUT_MANIFEST.json')==pre['origin_manifest']['sha256']
 assert time.time()-datetime.datetime.fromisoformat(pre['time_utc']).timestamp()<1800,'STALE_ADMISSION_PREFLIGHT'
 assert pre['reserved_streams']['hits']==[]
 plan=json.loads(json.dumps(plan));plan.update(authorization='User explicitly authorized this bounded development in pasted prompt',original_plan_sha256=sha(R/'unattended/NEXT_PLAN.json'),std_route_training_cap=80,no_new_physics_after_hours=7.25,decision_final=True)
 plan['stages']=[dict(stage='STD_screen',training_episodes=40,evaluations=8),dict(stage='one_paired_STD_extension',training_episodes=40,evaluations=4),dict(stage='R1_R4',training_episodes=40,evaluations=8),dict(stage='extra_paired_development',training_episodes=0,evaluations=4),dict(stage='locked_final',training_episodes=0,evaluations=12)]
 return plan,manifest,identity

def main():
 p=argparse.ArgumentParser();p.add_argument('--inspect',action='store_true');p.add_argument('--prepare-authorized',action='store_true');p.add_argument('--start-authorized',action='store_true');a=p.parse_args()
 plan,manifest,identity=inspect()
 if not a.prepare_authorized:
  assert not a.start_authorized,'PREPARE_AUTHORIZATION_REQUIRED'
  print(json.dumps(dict(status='PREPARED_NOT_STARTED',limits=plan['limits'],STD_cap=80,cleanup_minutes=45,original_guards='all retained',preflight=True),indent=2));return
 assert a.start_authorized,'USE_COMBINED_EXPLICIT_AUTHORIZED_ACTIVATION'
 dest=R.parent/'rl_b_training_stability_reward_v1'
 assert dest.parent.resolve()==R.parent.resolve() and dest.resolve()!=R.resolve(),'INVALID_DESTINATION'
 assert not dest.exists(),'DESTINATION_EXISTS_USE_RECOVERY_NO_OVERWRITE'
 mem={line.split(':',1)[0]:int(line.split(':',1)[1].split()[0])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
 assert mem['MemAvailable']>=6*1024**3 and shutil.disk_usage(R.parent).free>=70*1024**3,'RESOURCE_ADMISSION'
 conflicts=[]
 for p in Path('/proc').glob('[0-9]*/cmdline'):
  try:
   args=p.read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if int(p.parent.name)!=os.getpid() and 'python' in args.split(' ')[0] and any(x in args for x in ['/scripts/campaign.py','/scripts/worker.py','/source_versions/']) and '/ihear-lab/rl_b_' in args:conflicts.append(int(p.parent.name))
  except (OSError,ValueError):pass
 assert not conflicts,'EXISTING_RESEARCH_COMPUTE:'+str(conflicts)
 dest.mkdir();shutil.copytree(S/'scripts',dest/'scripts')
 for sub in ['runtime','configs','audit','owned','jobs','analysis_tools']:(dest/sub).mkdir()
 for name in list(manifest)+['FROZEN_CONTRACT_MANIFEST.json','native_boundary_motion_audit.py']:
  target=dest/'runtime'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/'runtime'/name,target)
 for name in ['launch.py','preflight.py','original_next_launch.py','ISOLATED_TEMPLATE_IDENTITY.json']:
  shutil.copyfile(S/name,dest/'audit'/name)
 shutil.copyfile(S/'audit/PREFLIGHT.json',dest/'audit/ADMISSION_PREFLIGHT.json')
 shutil.copyfile('/home/hank/.codex/attachments/46364b43-4300-45a4-9f67-e5aa3037412e/Pasted text.txt',dest/'audit/USER_AUTHORIZATION.txt')
 if (S/'analysis_tools').exists():
  for source in (S/'analysis_tools').iterdir():shutil.copyfile(source,dest/'analysis_tools'/source.name)
 # Reverify byte identities after copy, before clock activation or child creation.
 for name,h in manifest.items():assert sha(dest/'runtime'/name)==h,'COPY_RUNTIME_MISMATCH'
 for name,h in identity['files'].items():
  if name.startswith('scripts/'):assert sha(dest/name)==h,'COPY_SCRIPT_MISMATCH'
 current=datetime.datetime.now(datetime.timezone.utc);hard=current+datetime.timedelta(hours=8)
 put(dest/'START.json',dict(t0_utc=current.isoformat(),t0_local=current.astimezone(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),hard_stop_utc=hard.isoformat(),no_new_training_utc=(current+datetime.timedelta(hours=6)).isoformat(),no_new_physics_utc=(current+datetime.timedelta(hours=7.25)).isoformat(),limits=plan['limits'],origin_package=str(R),mode='BOUNDED_DEVELOPMENT_NEXT_STAGE'))
 put(dest/'ACTIVATION.json',dict(plan,training_authorized_for_next_stage=True,activation_utc=current.isoformat(),script_sha256={p.name:sha(p) for p in (dest/'scripts').glob('*.py')},contract_sha256=plan['checkpoint_pair'][0]['contract_sha256'],official_launcher_sha256=identity['official_launcher_sha256'],source_amendment='Isolated v2: enforce user STD80 and cleanup45; compare screens before extension; retain all original guards; add preflight and complete final locks',authorization_sha256=sha(dest/'audit/USER_AUTHORIZATION.txt')))
 put(dest/'RESEARCH_STATE.json',dict(status='PREPARED',phase='AUTHORIZED_START',time_utc=current.isoformat()))
 spec=importlib.util.spec_from_file_location('reward_manifest',dest/'scripts/rewards.py');reward=importlib.util.module_from_spec(spec);spec.loader.exec_module(reward)
 put(dest/'REWARD_VERSION_MANIFEST.json',dict(source_sha256=sha(dest/'scripts/rewards.py'),versions=reward.VERSIONS,active_training=['R1','R4'],evaluation_contract='Original unmodified R0/scorer; full task first'))
 env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','IHEAR_RESEARCH_ROOT':str(dest),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','CUDA_VISIBLE_DEVICES':'','IHEAR_GUARDED':'1'}
 services=[]
 try:
  for name,args in [('watchdog',[]),('failsafe',[]),('reporter',[]),('campaign',['--run-approved-plan'])]:
   with (dest/f'{name}.stdout.log').open('w') as stdout,(dest/f'{name}.stderr.log').open('w') as stderr:
    child=subprocess.Popen([str(PYTHON),str(dest/'scripts'/f'{name}.py'),*args],cwd=dest,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
    fields=Path(f'/proc/{child.pid}/stat').read_text();parts=fields[fields.rfind(')')+2:].split();services.append(dict(name=name,pid=child.pid,start_ticks=parts[19]))
 finally:put(dest/'LAUNCHED_SERVICES.json',dict(time_utc=current.isoformat(),services=services))
 print(json.dumps(dict(started=str(dest),ACTIVATION_UTC=current.isoformat(),hard_stop_utc=hard.isoformat(),no_new_physics_utc=(current+datetime.timedelta(hours=7.25)).isoformat(),STD_route_cap=80,services=services),indent=2),flush=True)
if __name__=='__main__':main()
