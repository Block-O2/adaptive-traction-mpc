"""Inspect by default. Preparation/start requires explicit next-stage CLI flags."""
from pathlib import Path
import os,sys,json,argparse,hashlib,shutil,datetime,subprocess,time
R=Path(__file__).resolve().parents[1];T=R/'unattended/template';PYTHON=R.parent/'rl_b_matched_recovery_stability_v1/cpu-env/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.writing')
 with tmp.open('w') as f:json.dump(x,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
def inspect():
 plan=json.loads((R/'unattended/NEXT_PLAN.json').read_text());identity=json.loads((R/'unattended/TEMPLATE_IDENTITY.json').read_text())
 for name,h in identity['files'].items():assert sha(T/name)==h,'TEMPLATE_SOURCE_CHANGED:'+name
 manifest=json.loads((R/'runtime/FROZEN_CONTRACT_MANIFEST.json').read_text())['files']
 for name,h in manifest.items():assert sha(R/'runtime'/name)==h,'RUNTIME_SOURCE_CHANGED:'+name
 for item in plan['checkpoint_pair']:
  for name,h in item['files'].items():assert sha(R.parent/'rl_b_autonomous_stability_reward_v1'/name)==h,'PARENT_IDENTITY_CHANGED'
 assert plan['limits']['training_attempts']==160 and plan['limits']['evaluation_attempts']==36 and plan['limits']['native_steps']==33000000
 return plan,manifest

def main():
 p=argparse.ArgumentParser();p.add_argument('--inspect',action='store_true');p.add_argument('--prepare-authorized',action='store_true');p.add_argument('--start-authorized',action='store_true');p.add_argument('--destination',type=Path);a=p.parse_args();plan,manifest=inspect()
 if not a.prepare_authorized:
  assert not a.start_authorized,'PREPARE_AUTHORIZATION_REQUIRED'
  print(json.dumps(dict(status='PREPARED_NOT_STARTED',methods=plan['methods'],limits=plan['limits'],holdout_reserve=12,requires_next_stage_authorization=True),indent=2));return
 assert plan['decision_final'],'ALL_ATTENDED_ABLATION_RESULTS_REQUIRED_BEFORE_NEXT_STAGE_PREPARATION'
 dest=a.destination or R.parent/'rl_b_training_stability_reward_v1'
 assert dest.parent.resolve()==R.parent.resolve() and dest.resolve()!=R.resolve(),'INVALID_DESTINATION'
 assert not dest.exists(),'DESTINATION_EXISTS_USE_NEW_VERSION_OR_READ_RECOVERY_GUIDE'
 dest.mkdir();shutil.copytree(T/'scripts',dest/'scripts')
 for sub in ['runtime','configs','audit','owned','jobs']:(dest/sub).mkdir()
 for name in list(manifest)+['FROZEN_CONTRACT_MANIFEST.json','native_boundary_motion_audit.py']:
  target=dest/'runtime'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/'runtime'/name,target)
 current=datetime.datetime.now(datetime.timezone.utc);hard=current+datetime.timedelta(hours=8)
 put(dest/'START.json',dict(t0_utc=current.isoformat(),t0_local=current.astimezone(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),hard_stop_utc=hard.isoformat(),no_new_training_utc=(current+datetime.timedelta(hours=6)).isoformat(),limits=plan['limits'],origin_package=str(R),mode='BOUNDED_DEVELOPMENT_NEXT_STAGE'))
 put(dest/'ACTIVATION.json',dict(plan,training_authorized_for_next_stage=bool(a.start_authorized),activation_utc=current.isoformat(),script_sha256={p.name:sha(p) for p in (dest/'scripts').glob('*.py')},contract_sha256=plan['checkpoint_pair'][0]['contract_sha256']))
 put(dest/'RESEARCH_STATE.json',dict(status='PREPARED',phase='AWAITING_EXPLICIT_START',time_utc=current.isoformat()))
 print('prepared',dest,flush=True)
 if not a.start_authorized:return
 env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','IHEAR_RESEARCH_ROOT':str(dest),'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','CUDA_VISIBLE_DEVICES':'','IHEAR_GUARDED':'1'}
 services=[]
 for name,args in [('watchdog',[]),('failsafe',[]),('reporter',[]),('campaign',['--run-approved-plan'])]:
  with (dest/f'{name}.stdout.log').open('w') as stdout,(dest/f'{name}.stderr.log').open('w') as stderr:
   child=subprocess.Popen([str(PYTHON),str(dest/'scripts'/f'{name}.py'),*args],cwd=dest,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
   fields=Path(f'/proc/{child.pid}/stat').read_text();parts=fields[fields.rfind(')')+2:].split();services.append(dict(name=name,pid=child.pid,start_ticks=parts[19]))
 put(dest/'LAUNCHED_SERVICES.json',dict(time_utc=current.isoformat(),services=services));print('started explicitly authorized finite development schedule',flush=True)

if __name__=='__main__':main()
