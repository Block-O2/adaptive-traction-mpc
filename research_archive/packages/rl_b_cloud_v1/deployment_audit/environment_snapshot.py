import json,platform,os,sys,subprocess,pathlib,datetime,hashlib,importlib.metadata as m
r=pathlib.Path(__file__).resolve().parents[1]
def command(args):
 p=subprocess.run(args,text=True,capture_output=True);return {'argv':args,'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'user':os.getlogin() if os.environ.get('USER') is None else os.environ['USER'],'hostname':platform.node(),'python':sys.version,'os':platform.platform(),'cpu_count':os.cpu_count(),'affinity':sorted(os.sched_getaffinity(0)),'packages':{n:m.version(n) for n in ['pip','mujoco','numpy','scipy','gymnasium','stable-baselines3','torch']},'commands':[command(x) for x in [['cat','/etc/os-release'],['lscpu'],['free','-b'],['df','-B1',str(r)],['dpkg-query','-W','-f=${Package} ${Status} ${Version}\n','python3.12-venv','libgl1','libegl1','libglfw3'],['git','-C','/home/hank','status','--short'],['git','-C','/home/hank','rev-parse','HEAD']]]}
import torch,mujoco
out['torch_cuda_build']=torch.version.cuda;out['torch_cuda_available']=torch.cuda.is_available();out['venv_prefix']=sys.prefix
(r/'deployment_audit/ENVIRONMENT_SNAPSHOT.json').write_text(json.dumps(out,indent=2))
print(json.dumps({k:v for k,v in out.items() if k!='commands'},indent=2))
