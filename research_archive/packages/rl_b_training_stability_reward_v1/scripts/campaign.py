"""Finite authorized v2 development study: STD <=80, total training <=160."""
from pathlib import Path
import os,sys,json,time,fcntl,subprocess
from research_common import ROOT,RUNTIME,HARD_STOP,NO_TRAIN,atomic,read,append,sha,now,pid_identity,check_resources,decision
from run_job import run_job
from finite_engine import GlobalStop,BranchFailure,classify
SEEDS=[1495656323,1630784693]

def verify_source_identity():
 for name,h in read(ROOT/'ACTIVATION.json')['script_sha256'].items():
  if sha(ROOT/'scripts'/name)!=h:raise GlobalStop('SOURCE_CHANGED:'+name)

def run(config):
 verify_source_identity();check_resources()
 if time.time()>=HARD_STOP-2700:raise BranchFailure('ORDERLY_NO_NEW_PHYSICS_WINDOW')
 ledger=read(ROOT/'LEDGER.json',dict(native_steps=0,training_attempts=0,evaluation_attempts=0,attempts=[]))
 limits=read(ROOT/'START.json')['limits'];final=config['job_id'].startswith('LOCKED_FINAL_')
 if any(not x['settled'] for x in ledger['attempts']):raise GlobalStop('UNCLOSED_OWNER_OR_RESERVATION')
 if config['mode']=='training':
  if ledger['training_attempts']+config['episodes']>limits['training_attempts']:raise BranchFailure('ORDERLY_TRAINING_BUDGET')
  if time.time()+config['episodes']*300+150>=NO_TRAIN:raise BranchFailure('ORDERLY_NO_NEW_TRAINING_WINDOW_RESERVE_WORST_JOB_TIME')
  if config['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']:
   used=sum(x['kind']=='training' and x['job'].split('_seed')[0] in ['CHECKPOINT_STD','STD_INIT_0p2'] for x in ledger['attempts'])
   if used+config['episodes']>80:raise BranchFailure('STD_ROUTE_80_EPISODE_CAP')
 reserve_native=0 if final else 12*165000
 if ledger['native_steps']+165000+reserve_native>limits['native_steps']:raise BranchFailure('ORDERLY_NATIVE_ALLOCATION_CLOSED_FINAL_RESERVE_PROTECTED')
 if config['mode']=='evaluation' and ledger['evaluation_attempts']+(0 if final else 12)>=limits['evaluation_attempts']:raise BranchFailure('ORDERLY_EVALUATION_ALLOCATION_CLOSED')
 p=ROOT/'configs'/f'{config["job_id"]}.json'
 if p.exists():assert read(p)==config,'CONFIG_CHANGED_ON_RESUME'
 else:atomic(p,config)
 end=run_job(p)
 if not end.get('success'):
  errors=json.dumps(end);current=read(ROOT/'LEDGER.json',dict(attempts=[]))
  prephysical=not any(x['job']==config['job_id'] for x in current['attempts'])
  known_local=any(x in errors for x in ['PARTIAL_PARENT_REQUIRES_EXPLICIT_RECOVERY','PENDING_BUFFER_REQUIRES_AGGREGATE_ROLLOUT','PENDING_BUFFER_REWARD_MISMATCH'])
  if prephysical and known_local and end.get('child_joined') and (end.get('worker_end') or {}).get('owner_joined'):
   end=dict(end,safe_branch_failure=True,classification_evidence='Known prephysical branch recovery denial; owner joined; preserve original artifacts')
 append(ROOT/'JOB_RESULTS.jsonl',dict(time_utc=now(),config_sha256=sha(p),end=end))
 if classify(end)=='GLOBAL':raise GlobalStop(json.dumps(end))
 if classify(end)=='BRANCH':raise BranchFailure(json.dumps(end))
 result=read(RUNTIME/'jobs'/config['job_id']/'RESULT.json')
 if config['mode']=='training':
  assert result['checkpoint'],'MISSING_CHECKPOINT'
  record=read(Path(result['checkpoint']).with_suffix('.json'))
  assert not record.get('pending_complete_transitions',0),'ENDPOINT_PENDING_REQUIRES_RECOVERY'
 decision('BRANCH_SEGMENT_COMPLETE',dict(job=config['job_id'],successes=result['successes'],episodes=result['episodes'],checkpoint=result['checkpoint']), 'Continue preregistered finite queue')
 return result

def train(label,seed,parent,start,count,reward='R1',initialize_std=None):
 return run(dict(job_id=f'{label}_seed{seed}_to{start+count:03d}',branch=label,seed=seed,parent_checkpoint=parent,start_episode=start,episodes=count,mode='training',learning_rate=.0003,rollout='aggregate64',reward=reward,target_kl=None,rollout_terminal_episode=start+count,std_initialization=initialize_std,carry_complete_pending=True,durable_pending_each_episode=True,aggregate_transitions=64))['checkpoint']

def evaluate(label,seed,parent,endpoint,mode,rng=2026102201,split='development'):
 return run(dict(job_id=f'{label}_seed{seed}_ep{endpoint:03d}_{mode}_{rng}',branch=label,seed=seed,parent_checkpoint=parent,start_episode=endpoint,episodes=1,mode='evaluation',learning_rate=0.,rollout='aggregate64',reward='R0',target_kl=None,policy_mode=mode,evaluation_rng=rng,evaluation_split=split))['rows'][0]

def endpoint(label,cps,n):
 return [evaluate(label,seed,cps[seed],n,mode) for seed in SEEDS for mode in ['deterministic','stochastic']]
def retention(rows):return len(rows)==4 and all(x['success'] for x in rows if x['policy_mode']=='deterministic')
def rank(rows):return (sum(x['success'] for x in rows if x['policy_mode']=='deterministic'),sum(x['success'] for x in rows if x['policy_mode']=='stochastic'),-sum(x['rejections'] for x in rows))
def branch_failure(label,exc):
 append(ROOT/'BRANCH_DECISIONS.jsonl',dict(time_utc=now(),branch=label,status='BRANCH_FAIL_CONTINUE',error=str(exc)))
 decision('BRANCH_FAILURE',dict(branch=label,error=str(exc)),'Preserve evidence; continue other authorized hypotheses')

def lock_final(final):
 activation=read(ROOT/'ACTIVATION.json')
 identity={str(seed):{suffix:sha(Path(cp).with_suffix(suffix)) for suffix in ['.zip','.rng.pt','.json']} for seed,cp in final['checkpoints'].items()}
 lock=dict(time_utc=now(),**final,checkpoint_sha256=identity,training_source_sha256=activation['script_sha256'],reward_definition=read(ROOT/'REWARD_VERSION_MANIFEST.json'),contract_sha256=activation['contract_sha256'],seeds=SEEDS,execution_mode='stochastic actual learned checkpoint Gaussian, raw then original clip',streams=activation['holdout_streams'],metrics=['runtime complete','full JF','full JM','tracking','native jerk','RETURN overshoot','admission/fallback'],promotion='Development nominal only; no post-holdout training or tuning; G4/Stage2/final Campaign remain closed')
 assert not (ROOT/'FINAL_SELECTION_BEFORE_HOLDOUT.json').exists()
 atomic(ROOT/'FINAL_SELECTION_BEFORE_HOLDOUT.json',lock)
 atomic(ROOT/'FINAL_SELECTION_LOCK_SHA256.json',dict(sha256=sha(ROOT/'FINAL_SELECTION_BEFORE_HOLDOUT.json')))
 return lock

def main():
 assert '--run-approved-plan' in sys.argv,'ACTIVATION_AND_AUTHORIZATION_FLAG_REQUIRED'
 activation=read(ROOT/'ACTIVATION.json');assert activation and activation['training_authorized_for_next_stage']
 verify_source_identity();assert not (ROOT/'END.json').exists(),'ALREADY_CLOSED'
 atomic(ROOT/'CAMPAIGN_PROCESS.json',dict(time_utc=now(),identity=pid_identity(os.getpid()),finite=True))
 methods=activation['methods'];parents={int(x['seed']):x['checkpoint'] for x in activation['checkpoint_pair']};cohorts={};status='RUNNING';error=None
 decision('ACTIVATED',{'activation_utc':activation['activation_utc'],'STD_cap':80},'Screen both STD methods before allocating one paired extension')
 try:
  for method in methods:
   cps={}
   try:
    for seed in SEEDS:cps[seed]=train(method,seed,parents[seed],0,10,initialize_std=.2 if method=='STD_INIT_0p2' else None)
    rows=endpoint(method,cps,10)
    cohorts[method]=dict(checkpoints=cps,rows=rows,endpoint=10)
    atomic(ROOT/f'{method}_SCREEN10.json',cohorts[method])
    if not retention(rows):decision('STD_SCREEN_FAILED',{'method':method,'rank':rank(rows)},'Continue other method and reward research')
   except BranchFailure as exc:branch_failure(method,exc)
   atomic(ROOT/'RESEARCH_STATE.json',dict(status='RUNNING',phase='STD_SCREEN',time_utc=now(),cohorts=cohorts))
  eligible=[m for m in cohorts if retention(cohorts[m]['rows'])]
  selected=max(eligible,key=lambda m:(rank(cohorts[m]['rows']),m=='CHECKPOINT_STD')) if eligible else 'BASELINE_STD_INIT_0p2'
  if eligible:
   cps=cohorts[selected]['checkpoints'];n=10
   if any(x['success'] for x in cohorts[selected]['rows'] if x['policy_mode']=='stochastic'):
    try:
     ext={seed:train(selected,seed,cps[seed],10,20) for seed in SEEDS}
     extrows=endpoint(selected,ext,30)
     atomic(ROOT/f'{selected}_EXTENSION30.json',dict(checkpoints=ext,rows=extrows,endpoint=30))
     if retention(extrows):cps=ext;n=30
     else:decision('EXTENSION_FAILED_PRESERVE_SCREEN',{'method':selected,'rank':rank(extrows)},'Use preserved 10-episode pair for reward forks')
    except BranchFailure as exc:branch_failure(selected+'_EXTENSION',exc)
  else:
   cps=parents;n=60
   atomic(ROOT/'NO_STABLE_TRAINING_METHOD.json',dict(reason='No trained method retained both mean endpoints',next='Independent R1/R4 test from immutable original R1/60; uniform STD=.2 initialization, inherited optimizer and fresh rollouts'))
  atomic(ROOT/'TRAINING_METHOD_SELECTION.json',dict(time_utc=now(),method=selected,checkpoints=cps,endpoint=n,rankings={m:rank(c['rows']) for m,c in cohorts.items()},criterion='Screen both; mean retention, sample completion, rejection count; checkpoint STD exact tie; only one method may extend; STD total <=80'))
  reward_cohorts={};initialize=.2 if not eligible else None
  atomic(ROOT/'REWARD_EXPERIMENT_LOCK.json',dict(time_utc=now(),selected_method=selected,parents=cps,std_initialization=initialize,optimizer='Full Adam inherited including log_std moments; never reset',rewards=['R1','R4'],episodes_per_branch=10,source_sha256=activation['script_sha256'],promotion='Both-parent equal-duration mean retained; sample completion not lower; both JM decrease; JF<=1.01*control; tolerance is development allocation only'))
  for reward in ['R1','R4']:
   label=f'REWARD_{reward}_{selected}';rcps={}
   try:
    for seed in SEEDS:rcps[seed]=train(label,seed,cps[seed],0,10,reward=reward,initialize_std=initialize)
    rr=endpoint(label,rcps,10);reward_cohorts[reward]=dict(checkpoints=rcps,rows=rr)
    atomic(ROOT/f'{reward}_REWARD_ENDPOINT.json',reward_cohorts[reward])
   except BranchFailure as exc:branch_failure(label,exc)
  final=dict(method=selected if eligible else 'ORIGINAL_CHECKPOINT_STD',reward='R1',checkpoints=cps,endpoint=n,reason='Preserve stable incumbent unless trained comparison qualifies')
  if 'R1' in reward_cohorts and retention(reward_cohorts['R1']['rows']):final.update(method=selected,checkpoints=reward_cohorts['R1']['checkpoints'],endpoint=10,reason='Matched R1 reward control retained')
  if all(k in reward_cohorts and retention(reward_cohorts[k]['rows']) for k in ['R1','R4']):
   good=rank(reward_cohorts['R4']['rows'])[:2]>=rank(reward_cohorts['R1']['rows'])[:2]
   for seed in SEEDS:
    a=next(x for x in reward_cohorts['R1']['rows'] if x['seed']==seed and x['policy_mode']=='deterministic');b=next(x for x in reward_cohorts['R4']['rows'] if x['seed']==seed and x['policy_mode']=='deterministic')
    good &= abs(a['task_s']-b['task_s'])<1e-7 and b['JM']<a['JM'] and b['JF']<=a['JF']*1.01
   if good:final.update(method=selected,reward='R4',checkpoints=reward_cohorts['R4']['checkpoints'],endpoint=10,reason='Both-parent moment-price development rule passed; no formal qualification')
  # Optional diagnostic slots (at most four) are paired fresh sample streams, never new training.
  available=24-read(ROOT/'LEDGER.json')['evaluation_attempts']
  if available>=4 and time.time()+4*300+2700<HARD_STOP:
   control=reward_cohorts.get('R1',{'checkpoints':cps});candidate=reward_cohorts.get('R4',{'checkpoints':cps})
   if 'R1' in reward_cohorts and 'R4' in reward_cohorts:
    for seed in SEEDS:
     for label,cohort in [('R1',control),('R4',candidate)]:evaluate('PAIRED_DEV2_'+label,seed,cohort['checkpoints'][seed],10,'stochastic',2026102202)
    decision('EXTRA_PAIRED_DEVELOPMENT',{'stream':2026102202,'attempts':4},'Report only; fixed primary reward selection criterion remains unchanged')
  atomic(ROOT/'REWARD_COHORT_SUMMARY.json',reward_cohorts)
  lock=lock_final(final)
  final_rows=[]
  for seed in SEEDS:
   for rng in activation['holdout_streams']:
    assert sha(ROOT/'FINAL_SELECTION_BEFORE_HOLDOUT.json')==read(ROOT/'FINAL_SELECTION_LOCK_SHA256.json')['sha256']
    for suffix,h in lock['checkpoint_sha256'][str(seed)].items():assert sha(Path(final['checkpoints'][seed]).with_suffix(suffix))==h
    final_rows.append(evaluate('LOCKED_FINAL',seed,final['checkpoints'][seed],final['endpoint'],'stochastic',rng,'reserved_action_streams'))
    atomic(ROOT/'FINAL_HOLDOUT_PROGRESS.json',dict(rows=final_rows,planned=12,candidate_locked=True))
  atomic(ROOT/'FINAL_HOLDOUT_RESULTS.json',dict(rows=final_rows,split='nominal action-stream only',training_after_final_selection=False))
  status='FINITE_QUEUE_COMPLETE_AWAITING_INDEPENDENT_REVIEW'
 except BranchFailure as exc:status='BOUNDED_ALLOCATION_CLOSED_PRESERVE_RESULTS';error=repr(exc)
 except BaseException as exc:status='GLOBAL_STOP';error=repr(exc)
 finally:
  atomic(ROOT/'RESEARCH_STATE.json',dict(status=status,time_utc=now(),error=error))
  atomic(ROOT/'CAMPAIGN_QUEUE_END.json',dict(status=status,time_utc=now(),error=error,final_campaign=False))
  subprocess.run([sys.executable,str(ROOT/'scripts/close_campaign.py')],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},timeout=max(1,min(2700,HARD_STOP-time.time()-5)))

if __name__=='__main__':
 with (ROOT/'.campaign.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);main()
