"""Root exact-config review for new fixed development diagnostics; no dispatch.
Expected SHA must be supplied from the already-built reviewed registration.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import time

P=Path(__file__).resolve().parents[1]
CASES={
 'V8DEVCAP01H':('V8BETA01H','305b90192d653a234f2375e23d99ee98fe9ed9030239a05c767a8133d90164e9',2026102751),
 'V8DEVCAP01L':('V8BETA01L','cf2b735402009a7a15f6b8aff01c759579c4cfb93ac0301cc0f18803407d1ece',2026102752),
 'V8POSTAPP01':('V8VAL03','cb5e746e608b60c11154b0607a27620b2a86e6f95d3370799b70861792d9e28c',2026102753),
 'V8POSTAPP02':('V8VAL04','224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87',2026102754),
}
MANDATORY=['V8VAL03','V8VAL04','V8FMEAN03','V8FMEAN04','V8CONVAL01','V8CONVAL02']
MASTER='freeze/COMPLETE_MODEL_PROCEDURE_PREVALIDATION_MASTER_V1.json'


def read(rel):return json.loads((P/rel).read_text())


def sha(rel):
 target=(P/rel).resolve();assert target.is_relative_to(P)
 return hashlib.sha256(target.read_bytes()).hexdigest()


def ref(rel):return dict(path=rel,sha256=sha(rel))


def ticks(pid):
 try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
 except FileNotFoundError:return None


def main():
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--group',choices=CASES,required=True);cli.add_argument('--expected-sha256',required=True);args=cli.parse_args();g=args.group
 assert time.time()<1793111740.0
 rel='experiments/'+g+'.json';assert sha(rel)==args.expected_sha256
 c=read(rel);old_group,case_sha,seed=CASES[g];old=read('experiments/'+old_group+'.json')
 assert c['group']==g and c['case_sha256']==case_sha==sha(c['case_path']) and c['condition']['seed']==seed
 assert c['condition']['prefix']==old['condition']['prefix']
 assert c['B']==old['B'] and c['H150']==old['H150'] and c['fork_phase']=='OUTBOUND' and c['fork_slot']==0
 assert c['worker']=='v8_worker_v2.py' and c['job_wall_cap_s']==1800 and not c.get('onpolicy_sampling')
 assert c['historical_repeats']=={} and c['local_stop_unix']==1793112940.0
 if g.startswith('V8DEVCAP'):
  h='families/ppo_reward/continuous_scale_v1/development_axis_capacity_v1/'
  registration=read(h+'ACTUAL_REGISTRATION_V1.json');entry=next(x for x in registration['configs'] if x['path']==rel);assert entry['sha256']==args.expected_sha256
  assert c['scientific_branch']=='EXPOSED_DEVELOPMENT_CAPABILITY_NOT_NEW_VALIDATION_NOT_TRAINING'
  assert c['algorithm']=='v8_fixed_development_axis_capacity_v1' and [x['tag'] for x in c['actions']]==['B','EARLY_H150']
  assert c['frozen_artifacts']['source/v8_fixed_development_axis_capacity_v1.py']=='45f6e1ab94d3bc7c5d11603a789df1d44a986678db341eb4738afead4b39a2cf'
  source_review='audit/DEVELOPMENT_AXIS_CAPACITY_MAIN_SOURCE_REVIEW_V1.json';mapping_calls=5;raw_compare_calls='original paid lambda1 repeat gate only';max_children=7
 else:
  h='families/critic_value/postvalidation_applicability_probe_v1/'
  registration=read(h+'prepared/MAIN_V2_ONCE/PREPARED_METADATA.json');assert registration['config_sha256'][g]==args.expected_sha256
  assert sha(h+'prepared/MAIN_V2_ONCE/'+g+'.json')==args.expected_sha256
  assert c['scientific_branch']=='EXPOSED_POSTVALIDATION_IMPLEMENTATION_CAPABILITY_DIAGNOSTIC_NOT_GENERALIZATION'
  assert c['algorithm']=='v8_postapp_fixed_v2'
  menu=read('freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json')['action_contracts']
  tags=['B','LATE_H150_APPLICABILITY','EARLY_H150_APPLICABILITY','LATE_PHASE_APPLICABILITY','EARLY_PHASE_APPLICABILITY'];assert [x['tag'] for x in c['actions']]==tags
  for i,entry in enumerate(c['actions']):
   action=dict(entry['action'])
   if i:assert action.pop('terminal_timing_applicability') is True
   assert action==menu[i]['action']
  assert c['frozen_artifacts']['source/v8_postapp_fixed_v2.py']=='0ef9b7e34258860a581c06a564dee9e0092dcf2c4dac1d3d27c5832dcdf9ce0e'
  source_review='audit/POSTAPP_MAIN_SOURCE_REVIEW_V2.json';mapping_calls=0;raw_compare_calls=1;max_children=5
 assert sha(MASTER)=='b7e41810af973c4af2fa9287c6801f37ae4ca0cee923e65e754c578ac83f728e'
 for f,expected in read(MASTER)['frozen_artifacts'].items():assert sha(f)==expected,f
 for f,expected in c['frozen_artifacts'].items():assert sha(f)==expected,f
 assert not (P/'jobs'/g).exists() and not (P/'owned'/('JOB_'+g+'.lock')).exists()
 events=[json.loads(x) for x in (P/'runtime/ATTEMPTS.jsonl').read_bytes().splitlines()]
 starts={x['id']:x for x in events if x.get('event')=='START'};ends={x['id']:x for x in events if x.get('event')=='END'}
 assert starts.keys()==ends.keys() and all(x.get('joined') is True for x in ends.values())
 groups={x['group'] for x in starts.values()};assert set(MANDATORY)<=groups;closures=[]
 for previous in sorted(groups):
  endrel='owned/'+previous+'_SUPERVISOR_END.json';end=read(endrel);begin=read('owned/'+previous+'_SUPERVISOR.json');assert end['state']=='STOP' and not end['survivors']
  for who in [begin['identity'],*end['known_owned'].values()]:assert ticks(who['pid'])!=who['start_ticks']
  closures.append(ref(endrel))
 ram=int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))*1024;disk=shutil.disk_usage(P).free;assert ram>=8*1024**3 and disk>=25*1024**3
 result=dict(status='ROOT_APPROVED_EXACT_FIXED_EXPOSED_DEVELOPMENT_DIAGNOSTIC',group=g,approved_unix=time.time(),
  config=ref(rel),source_review=ref(source_review),case_sha256=case_sha,seed=seed,verified_config_pins=len(c['frozen_artifacts']),
  original_master=ref(MASTER),original_master_pins_verified=2042,all_previous_physical_START_END=len(starts),previous_closed_supervisors=closures,
  additional_independent_condition_count=0,no_original_model_label_choice_transfer_or_fitting=True,new_model_fit_RNG_calls=0,
  future_pure_mapping_calls=mapping_calls,future_original_raw_comparison_scope=raw_compare_calls,registered_children=max_children,
  original_three_valued_hard_stops_and_full_TASK_and_motion_contract=True,physics_serial=True,job_wall_cap_s=1800,
  child_timeout_s=600,last_child_start_unix=1793111740.0,physics_stop_unix=1793112940.0,global_stop_unix=1793114740.0,
  free_ram_bytes=ram,free_disk_bytes=disk,preflight_source=ref(str(Path(__file__).relative_to(P))))
 target=P/'audit'/(g+'_MAIN_PHYSICS_APPROVAL_V1.json')
 with target.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
 print(json.dumps(dict(group=g,config_sha256=args.expected_sha256,pins=len(c['frozen_artifacts']),status=result['status'])))


if __name__=='__main__':main()
