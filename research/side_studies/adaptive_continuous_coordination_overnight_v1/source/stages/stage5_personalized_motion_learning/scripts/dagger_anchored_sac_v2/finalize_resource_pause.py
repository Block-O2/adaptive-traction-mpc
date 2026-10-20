"""Evidence-only resource pause closeout; no physics or learning is launched."""
from pathlib import Path
import json,time,os,signal,subprocess,hashlib
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1/source/stages/stage5_personalized_motion_learning');D=S/'docs/dagger_anchored_sac_v2';O=S/'results/dagger_anchored_sac_v2'
def save(name,v):
 for folder in (L,D):(folder/name).write_text(json.dumps(v,indent=2)+'\n')
def signal_saved_pause():
 row=json.loads((L/'RESOURCE_EXTERNAL.jsonl').read_text().splitlines()[-1]);pid=row['campaign_pid'];cmd=Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode();assert str(P/'train.py') in cmd
 children=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   st=dict(x.split(':',1) for x in (p/'status').read_text().splitlines() if ':' in x);c=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
   if int(st['PPid'].strip())==pid and str(P/'evaluate.py') in c:children.append(int(p.name))
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 assert not children,'WAIT_FOR_EXISTING_EVALUATION_TO_FINISH'
 save('RESOURCE_PAUSE_REQUEST.json',dict(unix=time.time(),pid=pid,reason='NEW_SWAP_OVER_128_MIB',observed_swap_bytes=row['swap_bytes'],limit_increment_bytes=128*2**20,training_steps_at_pause=21283,current_existing_evaluation_finished_before_interrupt=True,parameters_not_changed=True))
 os.kill(pid,signal.SIGINT);os.kill(pid,signal.SIGCONT)
def finalize():
 lines=[json.loads(x) for x in (L/'CHECKPOINTS.jsonl').read_text().splitlines()];last=lines[-1];assert last['total_online_steps']==21283;assert 'paused_exception_' in last['path'];result=json.loads((L/'RESULTS.json').read_text());known={r['name'] for r in result['evaluations']};new=[]
 # Recover a completed child result not yet acknowledged by the intentionally stopped parent.
 for p in sorted(L.glob('EVAL_*p10000*.json')):
  r=json.loads(p.read_text())
  if r['name'] not in known:new.append(r);known.add(r['name'])
 evalrows=[json.loads(x) for x in (L/'EVALUATIONS.jsonl').read_text().splitlines()];names={r['name'] for r in evalrows}
 for r in new:
  if r['name'] not in names:
   for folder in (L,D):
    with (folder/'EVALUATIONS.jsonl').open('a') as f:f.write(json.dumps(dict(unix=time.time(),recovered_completed_child_after_resource_pause=True,**r))+'\n')
   evalrows.append(r);names.add(r['name'])
 sources={json.loads(x)['source'] for x in (L/'BUDGET.jsonl').read_text().splitlines()};evalsteps=sum(r['steps'] for r in evalrows if r['name'] not in sources)
 for r in evalrows:r['used_for_training']=r['name'] in sources
 native=[r for r in evalrows if r['name'].startswith('legacy_predict_revision/checkpoint/a1_p10000_NATIVE_')];matched=[r for r in evalrows if r['name'].startswith('legacy_predict_revision/checkpoint/a1_p10000_MATCHED_')];stoch=[r for r in evalrows if r['name']=='legacy_predict_revision/checkpoint/a1_p10000_STOCHASTIC'];cp=next(p for p in (O/'checkpoints').iterdir() if p.name.startswith('candidate_attempt_1_point_010000_'));pause=dict(status='PAUSED_RESOURCE_RISK',reason='NEW_SWAP_OVER_128_MIB',total_online_steps=21283,actor_online_collection_steps=10000,initial_frozen_collection_steps=11283,evaluation_only_steps=evalsteps,rescues=0,resumable_checkpoint=last['path'],latest_native_good_checkpoint=str(cp),last_fully_evaluated_good_checkpoint=result['last_good'],confirmed_best=result['best'],latest_native_10000=native,latest_matched_10000=matched,latest_stochastic_10000=stoch,best_confirmation_pending='10000 Native 2/2 complete VALID; separately preregistered extra best replay not run because resource gate. Confirmed best retains 2000 checkpoint.',wall_s=time.time()-json.loads((L/'STATE.json').read_text())['started_unix'],no_new_physics_or_training_after_pause=True)
 save('FINAL_STATUS.json',dict(status=pause['status'],total_online_steps=21283,evaluation_only_steps=evalsteps,rescues=0,last_good=result['last_good'],best=result['best'],wall_s=pause['wall_s']));save('RESOURCE_PAUSE_CLOSEOUT.json',pause);result['evaluations']=evalrows;result.update(total_online_steps=21283,evaluation_only_steps=evalsteps,resource_pause=True,latest_native_complete_candidate=str(cp),extra_best_confirmation_pending=True);save('RESULTS.json',result);state=json.loads((L/'STATE.json').read_text());state.update(status=pause['status'],updated_unix=time.time(),total_online_steps=21283,error=pause['reason'],resumable_checkpoint=last['path'],next_action='STOP heavy simulation; resource review required before any continuation. Preserve original capacity/threshold configuration.');save('STATE.json',state);print(json.dumps({k:pause[k] for k in ('status','total_online_steps','evaluation_only_steps','resumable_checkpoint')}))
if __name__=='__main__':
 import sys
 signal_saved_pause() if len(sys.argv)>1 and sys.argv[1]=='signal' else finalize()
