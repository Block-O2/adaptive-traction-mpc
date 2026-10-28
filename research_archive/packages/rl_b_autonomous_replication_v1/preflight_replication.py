from pathlib import Path
import json,hashlib,subprocess,ast,time,sys
from common import ROOT,put
from checkpoints import sha
old=ROOT.parent/'rl_b_first_ppo_pilot_v1'
unchanged=['pilot_env.py','ready_env.py','training_env.py','pure_rl_env.py','native_rl_env.py','runtime_setup.py','native_journal.py','source_lookup_optimization.py','model_binary_cache.py','model_path_cache.py','independent_physics_audit.py','cloud_motion_audit.py']
checks={'unchanged_environment_reward_and_actor':all(sha(ROOT/p)==sha(old/p) for p in unchanged),'all_414_scientific_sources_unchanged':all(sha(ROOT/'source'/p)==v for p,v in json.loads((ROOT/'SOURCE_MANIFEST.json').read_text())['files'].items()),'no_historical_stop_files':not any((ROOT/p).exists() for p in ['STOP.json','RESOURCE_STOP','OBSERVER_STOP'])}
for p in ROOT.glob('*.py'):ast.parse(p.read_text())
checks['python_syntax']=True
from runtime_setup import install
install()
checks['frozen_vendor_dependencies_load']=True
cfg=json.loads((ROOT/'PPO_TRAINING_CONFIG.json').read_text());historical=json.loads((old/'PPO_TRAINING_CONFIG.json').read_text());checks['exact_stage1_ppo_hyperparameters']=cfg['ppo']==historical['ppo'];checks['new_distinct_seeds']=len(set(cfg['seeds']))==3 and historical['seed'] not in cfg['seeds']
for test in ['test_pilot_reward.py','test_execution_contract.py','test_safety_authority.py']:
 proc=subprocess.run([sys.executable,str(ROOT/test)],cwd=ROOT,capture_output=True,text=True,timeout=60)
 put(ROOT/'audit'/('PREFLIGHT_'+test+'.json'),{'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr});checks[test]=proc.returncode==0
put(ROOT/'PREFLIGHT_RESULTS.json',{'unix':time.time(),'checks':checks,'pass':all(checks.values()),'scope':'No new physical attempt; unit/source checks and historical development evidence only. G4_STRICT_PASS remains FAIL.'})
assert all(checks.values()),checks
# Contract protects training/evaluation executables, configs and all original sources.
files={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and ((p.parent==ROOT and p.suffix=='.py' and p.name not in ['freeze_protocol.py','preflight_replication.py']) or 'source' in p.relative_to(ROOT).parts or p.name in ['PPO_TRAINING_CONFIG.json','REPLICATION_PROTOCOL.json','STUDY_CONFIG.json','VENDOR_COPY_MANIFEST.json'])}
put(ROOT/'FROZEN_CONTRACT_MANIFEST.json',{'files':files})
from checkpoints import contract
put(ROOT/'LEVEL_A.json',{'status':'DEVELOPMENT_TRAINING_ALLOWED','contract_sha256':contract(),'scope':'Controlled replication of historical development environment; not formal B/H150 qualification.','checks':checks,'G4_STRICT_PASS':'FAIL','matched_evaluator':'NOT_READY_UNTIL_AUTHORITATIVE_SCORER_RECOVERED','historical_admission':sha(ROOT/'audit/HISTORICAL_LEVEL_A.json')})
print(json.dumps({'pass':True,'contract_sha256':contract(),'checks':checks}))
