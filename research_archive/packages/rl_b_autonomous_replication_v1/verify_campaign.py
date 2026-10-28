"""Final independent package/evidence audit. Never starts training or physics."""
from common import ROOT,put
from pathlib import Path
import json,time,hashlib,gzip,os,subprocess,math
from collections import Counter
from stream_json import read_evidence

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024**2),b''):h.update(x)
 return h.hexdigest()
def read(p):
 with read_evidence(p,encoding='utf-8') as f:return json.load(f)
def lines(p):return [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []
def verify(final=False):
 from checkpoints import contract
 cfg=read(ROOT/'PPO_TRAINING_CONFIG.json');ledger=read(ROOT/'LEDGER.json');train=lines(ROOT/'ALL_TRAINING_LOG.jsonl');ev=lines(ROOT/'ALL_EVALUATION_LOG.jsonl');checks={};details={}
 checks['execution_contract_unchanged']=contract()==read(ROOT/'LEVEL_A.json')['contract_sha256']
 checks['source_414_unchanged']=all(sha(ROOT/'source'/k)==v for k,v in read(ROOT/'SOURCE_MANIFEST.json')['files'].items())
 historical=read(ROOT/'audit/HISTORICAL_PROTECTION_BEFORE.json')['files'];changed=[p for p,m in historical.items() if not Path(p).is_file() or sha(Path(p))!=m['sha256']]
 checks['historical_4827_files_and_original_archives_unchanged']=not changed
 put(ROOT/'audit/HISTORICAL_PROTECTION_AFTER.json',{'unix':time.time(),'files_checked':len(historical),'changed_or_missing':changed,'all_unchanged':not changed,'checkpoints_and_zip_included':True})
 starts=list(ROOT.rglob('START.json'));missing=[str(p.relative_to(ROOT)) for p in starts if not (p.parent/'END.json').exists()]
 episode_starts=list(ROOT.rglob('EPISODE_START.json'));episode_missing=[str(p.relative_to(ROOT)) for p in episode_starts if not (p.parent/'EPISODE_END.json').exists()]
 attempts=[]
 for rel in ledger['physical_attempts']:
  p=ROOT/rel;start=read(p/'START.json');end=read(p/'END.json') if (p/'END.json').exists() else None
  attempts.append({'run':rel,'start':start,'end_status':None if end is None else end['status'],'owner_joined':False if end is None else end['owner_joined'],'native_steps':None if end is None else end.get('row',{}).get('native_steps',end.get('terminal_info',{}).get('native_steps_total') if end.get('terminal_info') else None)})
 physical_starts=[p for p in starts if p.parent.name.startswith('episode_') and p.parent.parent.name not in ['env']]
 checks['START_END_all_closed']=not missing and not episode_missing and all(x['owner_joined'] for x in attempts)
 checks['physical_START_matches_ledger']=len(physical_starts)==len(ledger['physical_attempts'])==ledger['stage1_attempts']+ledger['stage2_attempts']+ledger['evaluation_attempts']
 checks['budget_episode_caps']=ledger['stage1_attempts']<=240 and ledger['stage2_attempts']<=50 and ledger['evaluation_attempts']<=24
 checks['budget_native_decision_optimizer_caps']=ledger['native_steps']<=cfg['native_steps_hard_cap'] and ledger['rl_decisions']<=cfg['rl_decisions_hard_cap'] and ledger['optimizer_steps']<=cfg['optimizer_steps_hard_cap']
 # A partial infrastructure attempt remains in accounting even without a train row.
 checks['native_decision_update_totals']=sum(x['native_steps'] for x in train+ev)==ledger['native_steps'] and sum(x['decisions'] for x in train+ev)==ledger['rl_decisions'] and sum(len(x['gradient_steps']) for x in train)==ledger['optimizer_steps']
 checks['all_episode_saved_audits_pass']=all(x['independent_audit_pass'] for x in train+ev)
 accounting={'unix':time.time(),'all_START_count':len(starts),'all_END_count':len([p for p in ROOT.rglob('END.json')]),'missing_END':missing,'EPISODE_START_count':len(episode_starts),'EPISODE_END_count':len(list(ROOT.rglob('EPISODE_END.json'))),'missing_EPISODE_END':episode_missing,'physical_attempts':attempts,'ledger':ledger,'budget_caps':{'stage1':240,'stage2':50,'evaluation':24,'native':cfg['native_steps_hard_cap']},'all_closed':checks['START_END_all_closed'],'program_and_episode_records_are_not_extra_physical_attempts':True,'initial_dependency_packaging_failure':'Preserved zero-physics guard attempt in audit/guards/1106823814_initialize; no model, no native or Adam steps.'}
 put(ROOT/'ATTEMPT_ACCOUNTING.json',accounting)
 cps=[]
 for p in sorted((ROOT/'seeds').rglob('checkpoints/*.json')):
  x=read(p);base=p.with_suffix('');cps.append({'checkpoint':str(base.relative_to(ROOT)),'policy_sha256':x['policy_sha256'],'model_sha256':x['model_sha256'],'rng_sha256':x['rng_sha256'],'decisions':x['decisions'],'PPO_epochs':x['updates'],'Adam_updates':x.get('optimizer_step_calls'),'hash_pass':sha(base.with_suffix('.zip'))==x['model_sha256'] and sha(base.with_suffix('.rng.pt'))==x['rng_sha256'],'contract_pass':x['contract_sha256']==contract()})
 resumes=[read(p) for p in (ROOT/'seeds').rglob('RESUME_AUDIT.json')]
 initials=[read(ROOT/'seeds'/str(seed)/'stage1/checkpoints/initial.json') for seed in cfg['seeds']]
 checks['three_distinct_scratch_initializations']=len({x['policy_sha256'] for x in initials})==3 and all(x['initialization']=='SCRATCH_RANDOM' and x['updates']==0 and x['decisions']==0 and not x['teacher_used'] for x in initials)
 checks['dependency_version_parity']=read(ROOT/'audit/DEPENDENCY_VERSION_PARITY.json')['pass']
 checks['all_checkpoint_hashes_and_resumes']=bool(cps) and all(x['hash_pass'] and x['contract_pass'] for x in cps) and all(x['pass'] for x in resumes)
 put(ROOT/'PPO_CHECKPOINT_AUDIT.json',{'generations':cps,'resume_checks':resumes,'pass':checks['all_checkpoint_hashes_and_resumes'],'semantics':'Adam+Python/NumPy/Torch RNG; fresh physical episode. No mid-episode simulator restoration claim.'})
 # Every transition is stored; each trained rollout must use all transitions.
 rollout=[]
 import numpy as np
 for row in train:
  z=np.load(ROOT/row['run']/'transitions_0.npz');b=np.load(ROOT/row['run']/'ppo_rollout.npz');n=len(z['rewards']);rollout.append({'run':row['run'],'n_transitions':n,'n_used':len(b['rewards']),'pass':n==len(b['rewards'])==row['decisions'] and abs(float(z['rewards'].sum())-row['reward'])<1e-6 and bool(z['terminated'][-1] and not z['terminated'][:-1].any() and not z['truncated'].any())})
 checks['all_training_transitions_used_and_terminal']=all(x['pass'] for x in rollout)
 put(ROOT/'audit/ROLLOUT_UPDATE_ACCOUNTING.json',{'rows':rollout,'all_pass':checks['all_training_transitions_used_and_terminal']})
 # Actual evaluation raw is reread independently after training has ended.
 if final:
  from independent_physics_audit import audit as ownership
  owners=[]
  for row in ev:
   ep=ROOT/row['run']/'env/episode_0001';m=read(ep/'episode_summary.json');x=ownership(ep/'runtime_artifacts.json',m['physical_evaluation_only']['human_qpos_indices'],m['physical_evaluation_only']['human_dof_indices']);owners.append({'run':row['run'],**x});print(json.dumps({'final_raw_audit':row['run'],'pass':x['accounting_pass']}),flush=True)
  checks['evaluation_final_native_receipt_recomputation']=all(x['accounting_pass'] for x in owners)
  put(ROOT/'audit/FINAL_EVALUATION_NATIVE_RECOMPUTATION.json',{'episodes':owners,'all_pass':checks['evaluation_final_native_receipt_recomputation']})
 checks['evaluator_semantics_negative_tests']=read(ROOT/'EVALUATOR_SEMANTICS_TESTS.json')['pass']
 if final:
  checks['same_observation_policy_action_change']=read(ROOT/'audit/POLICY_ACTION_CHANGE.json')['all_pass']
  boundary=read(ROOT/'audit/EVALUATION_NATIVE_BOUNDARY_MOTION.json')
  checks['all_evaluation_native_TASK_boundary_windows']=boundary['all_pass'] and len(boundary['evaluations'])==len(ev)
  checks['analysis_code_identity_unchanged']=all(sha(ROOT/k)==v for k,v in read(ROOT/'ANALYSIS_MANIFEST.json')['files'].items())
  checks['orchestration_code_identity_unchanged']=all(sha(ROOT/k)==v for k,v in read(ROOT/'ORCHESTRATION_MANIFEST.json')['files'].items())
 metrics=read(ROOT/'audit/ALL_SCIENTIFIC_METRICS.json') if (ROOT/'audit/ALL_SCIENTIFIC_METRICS.json').exists() else None
 checks['force_tracking_native_metrics_recomputed']=metrics is not None and metrics['all_pass']
 host=lines(ROOT/'audit/HOST_RESOURCE_SAMPLES.jsonl');checks['RAM_reserve_6_GiB']=bool(host) and min(x['available_ram_bytes'] for x in host)>=6*1024**3
 checks['no_mujoco_or_resource_failure']=not (ROOT/'RESOURCE_STOP').exists() and all(not x['resource']['failure'] for x in train+ev)
 # Only train/eval/resource and orchestrator/observer processes count here.
 active=[]
 for line in subprocess.check_output(['ps','-eo','pid,ppid,args'],text=True).splitlines()[1:]:
  v=line.split(None,2)
  if len(v)!=3:continue
  if str(ROOT) in v[2] and v[2].startswith((str(ROOT.parent/'rl_b_cloud_v1/.venv/bin/python'),'python')) and any(n in v[2] for n in ['campaign_manager.py','replication_run.py','resource_guard.py','host_observer.py','stage2_manager.py']):active.append({'pid':int(v[0]),'ppid':int(v[1]),'command':v[2]})
 if final:checks['all_owned_training_simulation_observer_processes_exited']=not active
 put(ROOT/'PROCESS_EXIT_AUDIT.json',{'unix':time.time(),'active_owned_training_simulation_processes':active,'pass':not active,'verification_process_excluded':os.getpid()})
 result={'unix':time.time(),'category':'FINAL_INDEPENDENT_SAVED_EVIDENCE_VERIFICATION' if final else 'INTERIM_VERIFICATION','checks':checks,'pass':all(checks.values()),'failures':[k for k,v in checks.items() if not v],'no_formal_qualification_inferred':True,'audit_independence':'Separate raw-reading/recomputation code by one Agent; no independent second Agent or human review.'}
 put(ROOT/'VALIDATION_RESULTS.json',result)
 return result
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');a=p.parse_args();print(json.dumps(verify(a.final)))
