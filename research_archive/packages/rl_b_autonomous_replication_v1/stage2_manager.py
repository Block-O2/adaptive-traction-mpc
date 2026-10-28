"""Execute only a separately frozen Stage2 development gate, then exit."""
from pathlib import Path
import os,json,time,hashlib,subprocess,traceback,signal
R=Path(__file__).resolve().parent;PY=R.parent/'rl_b_cloud_v1/.venv/bin/python'
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
 cfg=json.loads((R/'PPO_TRAINING_CONFIG.json').read_text());frozen=json.loads((R/'STAGE2_FROZEN.json').read_text());identity=json.loads((R/'STAGE2_FROZEN_IDENTITY.json').read_text());seed=frozen['seed'];error=None;proc=None;stop_reason=None
 if not frozen['gate_pass']:raise RuntimeError('STAGE2_GATE_CLOSED')
 put(R/'audit/STAGE2_MANAGER_START.json',{'unix':time.time(),'pid':os.getpid(),'frozen_config_sha256':identity['sha256'],'category':'TASK_PRETRAINED_PPO_FINETUNING_NON_PROMOTION_DEVELOPMENT'})
 def run(mode,target=None,kind=None):
  nonlocal proc
  if hashlib.sha256((R/'STAGE2_FROZEN.json').read_bytes()).hexdigest()!=identity['sha256']:raise RuntimeError('STAGE2_CONFIG_CHANGED')
  if time.time()>=cfg['no_new_physics_after_unix']:raise RuntimeError('NO_NEW_PHYSICS_WINDOW')
  name=f'{seed}_stage2_{mode}'+(f'_{target}' if target else '')+(f'_{kind}' if kind else '')
  args=[str(PY),str(R/'replication_run.py'),'--mode',mode,'--seed',str(seed),'--stage','stage2']
  if target:args+=['--target',str(target)]
  if kind:args+=['--kind',kind]
  out=R/'audit/guards'/name;seconds=min(5000,cfg['no_new_physics_after_unix']-time.time());command=[str(PY),str(R/'resource_guard.py'),'--out',str(out),'--seconds',str(seconds),'--',*args]
  put(R/'audit'/('STAGE2_IDENTITY_'+name+'.json'),{'stage2_reward_config_sha256':identity['sha256'],'command':command,'inherited_pilot_metadata_note':'Generic PilotEnv EPISODE_START.reward/pilot_reward_contract describe the inherited Stage1 wrapper. stage2_reward_contract.json and public_reward_contract.json are authoritative for the executed Stage2 reward; independent audit explicitly reads Stage2 failure floor. No actor/native source edits.'})
  print(json.dumps({'event':'STAGE2_PROGRAM_START','name':name}),flush=True);proc=subprocess.Popen(command,cwd=R,start_new_session=True)
  try:rc=proc.wait(timeout=seconds+75)
  except subprocess.TimeoutExpired:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
   raise RuntimeError('STAGE2_OUTER_TIMEOUT')
  finally:proc=None
  if rc:raise RuntimeError('STAGE2_GUARDED_PROGRAM_FAILED:'+name)
 try:
  run('initialize')
  for target in [10,20,30]:
   run('train',target=target)
   p=R/'seeds'/str(seed)/'stage2/TRAINING_LOG.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()][-10:];rate=sum(x['success'] for x in rows)/len(rows);below=rate<frozen['parent_training_success_rate_last20']
   put(R/'audit'/f'STAGE2_BLOCK_{target:03d}.json',{'unix':time.time(),'target':target,'block_rate':rate,'parent_last20_rate':frozen['parent_training_success_rate_last20'],'stop_for_task_rate_drop':below,'stricter_than_protocol_20pp_rule':True})
   if below:stop_reason='TRAINING_TASK_COMPLETION_RATE_DROP';break
  run('evaluate',kind='stage2_final_first');run('evaluate',kind='stage2_final_repeat')
  progress=json.loads((R/'seeds'/str(seed)/'stage2/PROGRESS.json').read_text());put(R/'STAGE2_COMPLETE.json',{'unix':time.time(),'status':'STOPPED_TASK_RATE_DROP' if stop_reason else 'COMPLETED','stop_reason':stop_reason,'progress':progress,'frozen_config_sha256':identity['sha256'],'no_reward_revision':True,'no_final_campaign_started':True})
 except BaseException as e:error={'error':repr(e),'traceback':traceback.format_exc()};put(R/'audit/STAGE2_MANAGER_FAILURE.json',error);raise
 finally:
  if proc is not None and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=10)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=10)
  put(R/'audit/STAGE2_MANAGER_END.json',{'unix':time.time(),'pid':os.getpid(),'error':error,'stop_reason':stop_reason,'owned_child_joined':proc is None or proc.poll() is not None})
if __name__=='__main__':main()
