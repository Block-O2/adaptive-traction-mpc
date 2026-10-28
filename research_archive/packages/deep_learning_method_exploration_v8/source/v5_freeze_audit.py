"""Final pre-registration, validation alias and unchanged control-source audit."""
from pathlib import Path
import json,hashlib,datetime
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def read(n):return json.loads((P/n).read_text())
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
events=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];freeze=read('analysis/LOCKED_VALIDATION_SELECTION.json');source=read('audit/VALIDATION_CONTROL_SOURCE_FREEZE.json');errors=[];groups=[]
val_starts=[e for e in events if e['event']=='START' and e.get('group') in ['VAL01','VAL02','VAL03','VAL04']];assert val_starts,'NO_PRIMARY_VALIDATION_START'
first=min(e['unix'] for e in val_starts);source_time=datetime.datetime.fromisoformat(source['frozen_utc']).timestamp()
if source_time>=first or freeze['frozen_unix']>=first or datetime.datetime.fromisoformat(freeze['frozen_utc']).timestamp()>=first:errors.append('GLOBAL_FREEZE_NOT_BEFORE_FIRST_VAL_START')
source_bad=[r for r,h in source['files'].items() if not (P/r).is_file() or sha(P/r)!=h]
errors.extend(['FROZEN_CONTROL_SOURCE_CHANGED:'+r for r in source_bad])
initial=read('owned/VALIDATION3_QUEUE_START.json');conditions_file=P/'experiments/LOCKED_VALIDATION_INPUTS.json'
if initial['conditions_sha256']!=sha(conditions_file):errors.append('PREREGISTERED_CONDITIONS_CHANGED')
if datetime.datetime.fromisoformat(read('experiments/LOCKED_VALIDATION_INPUTS.json')['frozen_utc']).timestamp()>=first:errors.append('INPUTS_NOT_BEFORE_VAL_RESULTS')
expected={'B':{'family':'B'},'BEST':read('attempts/CORE01_BEST_RESULT.json')['action']};expected.update({name:value['action'] for name,value in freeze['selected'].items()});ppo={r['tag']:r['action'] for r in read('experiments/PPOCHECK.json')['actions']};expected.update(PPO_MEAN=ppo['FROZEN_MEAN'],PPO_RULE=ppo['FROZEN_PLUS_RULE'])
for item in freeze['configs']:
 group=item['group'];cfg=read('experiments/'+group+'.json');manifest=read('jobs/'+group+'/SOURCE_MANIFEST.json');bad=[]
 if item['config_sha256']!=sha(P/'experiments'/(group+'.json')) or manifest['config_sha256']!=item['config_sha256']:bad.append('FROZEN_CONFIG_CHANGED')
 common=set(manifest['files'])&set(source['files']);mismatch=[r for r in common if manifest['files'][r]!=source['files'][r]]
 if mismatch:bad.append('GLOBAL_SOURCE_IDENTITY_MISMATCH')
 tags={r['tag']:r for r in cfg['actions']};keys=[json.dumps(r['action'],sort_keys=True,separators=(',',':')) for r in cfg['actions']]
 if len(keys)!=len(set(keys)):bad.append('EXACT_ACTION_DUPLICATION')
 for name,canonical in cfg['validation_method_aliases'].items():
  if canonical not in tags or name not in expected or tags[canonical]['action']!=expected[name]:bad.append('METHOD_ALIAS_ACTION_NOT_IDENTICAL:'+name)
 for tag,entry in tags.items():
  actual=read('attempts/'+group+'_'+tag+'_RESULT.json')
  if actual['action']!=entry['action']:bad.append('ACTUAL_ACTION_CONFIG_MISMATCH:'+tag)
 end=read('owned/'+group+'_SUPERVISOR_END.json')
 if end['worker_exit_code']!=0:bad.append('VALIDATION_GROUP_NOT_CLOSED')
 groups.append(dict(group=group,status='PASS' if not bad else 'FAIL',common_frozen_source_files=len(common),actual_physical_candidates=len(tags),method_aliases=cfg['validation_method_aliases'],errors=bad));errors.extend([group+':'+x for x in bad])
supp=read('owned/PPO_REPAIR_QUEUE_START.json');supp_errors=[]
if datetime.datetime.fromisoformat(supp['utc']).timestamp()>=first:supp_errors.append('SUPPLEMENT_REGISTERED_AFTER_PRIMARY_VAL')
for group,h in supp['finite_configs'].items():
 if sha(P/'experiments'/(group+'.json'))!=h:supp_errors.append('SUPPLEMENT_CONFIG_CHANGED:'+group)
gate=read('analysis/PPO_REPAIR_GATE.json');supp_end=read('owned/PPO_REPAIR_QUEUE_END.json')
if gate['validation_triggered'] and 'PPOREPAIRVAL' not in supp_end['completed']:supp_errors.append('SUPPLEMENT_TEST_TRIGGERED_BUT_NOT_COMPLETE')
primary_end=read('owned/VALIDATION3_QUEUE_END.json');primary_end_time=datetime.datetime.fromisoformat(primary_end['utc']).timestamp();supp_starts=[e for e in events if e['event']=='START' and e.get('group') in ['PPOREPAIR01','PPOREPAIRVAL']]
if any(e['unix']<primary_end_time for e in supp_starts):supp_errors.append('SUPPLEMENT_PHYSICS_OVERLAPPED_PRIMARY_VALIDATION')
errors.extend(supp_errors)
compose=P/'analysis/PHASE_COMPOSITION_MODEL.json'
if compose.exists():
 model=json.loads(compose.read_text())
 if model['source_sha256']!=sha(P/'source/v5_phase_composition.py'):errors.append('COMPOSITION_PROTOCOL_SOURCE_CHANGED')
 if len(model['selected_proposals'])>3:errors.append('COMPOSITION_CANDIDATE_CAP')
 comp_starts=[e for e in events if e['event']=='START' and e.get('group')=='COMPOSE01']
 if comp_starts and datetime.datetime.fromisoformat(model['frozen_utc']).timestamp()>=min(e['unix'] for e in comp_starts):errors.append('COMPOSITION_MODEL_NOT_FROZEN_BEFORE_START')
out=dict(status='PASS' if not errors else 'FAIL',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),global_frozen_source_files=len(source['files']),first_primary_VAL_START_unix=first,source_freeze_UTC=source['frozen_utc'],candidate_and_config_freeze_UTC=freeze['frozen_utc'],groups=groups,supplementary_pre_registered_config_hashes=supp['finite_configs'],supplementary_errors=supp_errors,errors=errors,scope='Development-guided pre-registration is allowed. No unseen primary or supplemental validation outcome changes selected actions/configs. Exact aliases reuse one actual result and do not add physical attempts.',new_physical_START=0)
(P/'audit/FROZEN_VALIDATION_AND_PROTOCOL_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('FREEZE_PROTOCOL',out['status'],'groups',len(groups),'errors',errors);assert not errors,errors
