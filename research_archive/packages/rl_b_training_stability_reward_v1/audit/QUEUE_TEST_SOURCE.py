from pathlib import Path
import tempfile,os,json,sys,shutil,hashlib,time,importlib
s=Path(__file__).resolve().parent;r=Path(tempfile.mkdtemp(prefix='ihear_queue_test_'));shutil.copytree(s/'scripts',r/'scripts');(r/'runtime/jobs').mkdir(parents=True);(r/'configs').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
from datetime import datetime,timezone,timedelta
now=datetime.now(timezone.utc)
(r/'START.json').write_text(json.dumps(dict(t0_utc=now.isoformat(),hard_stop_utc=(now+timedelta(hours=8)).isoformat(),no_new_training_utc=(now+timedelta(hours=6)).isoformat(),limits=dict(training_attempts=160,evaluation_attempts=36,native_steps=33000000))))
(r/'ACTIVATION.json').write_text(json.dumps(dict(training_authorized_for_next_stage=True,activation_utc=now.isoformat(),methods=['CHECKPOINT_STD','STD_INIT_0p2'],checkpoint_pair=[dict(seed=x,checkpoint=str(r/f'parent{x}')) for x in [1495656323,1630784693]],script_sha256={p.name:sha(p) for p in (r/'scripts').glob('*.py')},contract_sha256='synthetic_contract',holdout_streams=list(range(2026102301,2026102307)))))
(r/'REWARD_VERSION_MANIFEST.json').write_text('{}')
for seed in [1495656323,1630784693]:
 for suffix in ['.zip','.rng.pt','.json']:(r/f'parent{seed}{suffix}').write_text('{}')
os.environ['IHEAR_RESEARCH_ROOT']=str(r);sys.path.insert(0,str(r/'scripts'));import campaign as c
c.check_resources=lambda:{}
mode=sys.argv[1];sys.argv=['campaign.py','--run-approved-plan'];seen=[]
def fakejob(path):
 cfg=json.loads(path.read_text());label=cfg['branch'];seed=cfg['seed'];n=cfg['episodes'];seen.append(cfg)
 l=c.read(r/'LEDGER.json',dict(training_attempts=0,evaluation_attempts=0,native_steps=0,attempts=[]));kind=cfg['mode'];l[kind+'_attempts']+=n
 for i in range(n):l['attempts'].append(dict(kind=kind,job=cfg['job_id'],settled=True))
 c.atomic(r/'LEDGER.json',l)
 cp=r/'runtime/jobs'/cfg['job_id']/'checkpoints'/f'episode_{cfg["start_episode"]+n:03d}';cp.parent.mkdir(parents=True)
 for suffix in ['.zip','.rng.pt','.json']:cp.with_suffix(suffix).write_text('{}')
 ok=not (mode=='STD_fail' and label in ['CHECKPOINT_STD','STD_INIT_0p2'])
 row=dict(seed=seed,success=ok,rejections=0,policy_mode=cfg.get('policy_mode','training'),task_s=19.03,JM=90. if 'REWARD_R4' in label else 100.,JF=1000.)
 result=dict(checkpoint=str(cp) if kind=='training' else None,rows=[row],successes=n if ok else 0,episodes=n)
 c.atomic(r/'runtime/jobs'/cfg['job_id']/'RESULT.json',result)
 return dict(success=True)
c.run_job=fakejob;c.subprocess.run=lambda *a,**k:None
c.main();state=c.read(r/'RESEARCH_STATE.json');assert state['error'] is None,state
std=sum(x['episodes'] for x in seen if x['mode']=='training' and x['branch'] in ['CHECKPOINT_STD','STD_INIT_0p2']);training=sum(x['episodes'] for x in seen if x['mode']=='training');evaluation=sum(x['episodes'] for x in seen if x['mode']=='evaluation');finals=[x for x in seen if x['job_id'].startswith('LOCKED_FINAL')]
assert std<=80 and training<=160 and evaluation<=36 and len(finals)==12
assert all(x['evaluation_split']=='reserved_action_streams' for x in finals)
assert any(x['branch'].startswith('REWARD_R4') for x in seen)
print(json.dumps(dict(scenario=mode,STD_training=std,training=training,evaluation=evaluation,finals=len(finals),pass_=True)))
