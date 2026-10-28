"""Pure-read evidence verifier. Only its new --out directory is writable.
No repair, scoring, integration, model import, process termination or experiment.
"""
from pathlib import Path
import argparse,collections,hashlib,json,os,re,resource,signal,sys,time,traceback
REQUIRED=['REPORT.md','EXPERIMENT_CONTRACT.md','BASELINE_AND_PAIRED_OPTIMIZATION.md','LEARNING_METHODS_AUDIT.md','CRITIC_AND_VALUE_RESULTS.md','RL_AND_REWARD_RESULTS.md','HISTORY_CONDITIONED_LEARNING.md','MOTION_FORCE_MOMENT_TRADEOFF.md','RELATED_WORK.md','LEARNING_CONTROL_INTERFACE_GUIDE.md','RESEARCH_DECISIONS.jsonl','RESOURCE_AND_ATTEMPT_ACCOUNTING.json','PACKAGE_VERIFICATION.json','NEXT_RESEARCH_DECISION.md','END.json']
PRESEAL_PENDING={'PACKAGE_VERIFICATION.json','END.json'}
def allowed_pending_report_link(package, report, target, stage):
 if stage!='preseal':return False
 resolved=(Path(report).parent/target).resolve()
 return resolved in {(Path(package)/name).resolve() for name in PRESEAL_PENDING}

def identity():return {'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])}
def pointer(d,key):
 for k in key.strip('/').split('/') if key.strip('/') else []:d=d[int(k)] if isinstance(d,list) else d[k.replace('~1','/').replace('~0','~')]
 return d
def pid_state(p):
 try:
  s=(Path('/proc')/str(p['pid'])/'stat').read_text().rsplit(')',1)[1].split()
  return 'REUSED_PID' if int(s[19])!=int(p['start_ticks']) else 'ZOMBIE' if s[0]=='Z' else 'LIVE'
 except (FileNotFoundError,ProcessLookupError):return 'ENDED'
def identities(d):
 if isinstance(d,dict):
  if isinstance(d.get('pid'),int) and isinstance(d.get('start_ticks'),int):yield {'pid':d['pid'],'start_ticks':d['start_ticks']}
  for x in d.values():yield from identities(x)
 elif isinstance(d,list):
  for x in d:yield from identities(x)
def join_ledger(rows):
 starts=collections.defaultdict(list);ends=collections.defaultdict(list);issues=[]
 for n,r in enumerate(rows):
  if r.get('event') not in ('START','END'):continue
  ident=r.get('id')
  if not isinstance(ident,str):issues.append({'code':'MISSING_LEDGER_ID','line':n+1});continue
  (starts if r['event']=='START' else ends)[ident].append(r)
 joined=[]
 for ident in sorted(set(starts)|set(ends)):
  s,e=starts[ident],ends[ident]
  if len(s)!=1 or len(e)!=1:issues.append({'code':'LEDGER_NOT_EXACT_ONE_START_ONE_END','id':ident,'START':len(s),'END':len(e)})
  if len(s)==len(e)==1:
   if e[0].get('group') not in (None,s[0].get('group')):issues.append({'code':'END_GROUP_CONFLICT','id':ident})
   if e[0].get('unix',0)<s[0].get('unix',0):issues.append({'code':'END_BEFORE_START','id':ident})
   joined.append({'id':ident,'group':s[0].get('group'),'START':s[0],'END':e[0]})
 return joined,issues
def classify(result,engineering=False):
 if engineering:return 'ENGINEERING_FAILURE_UNRANKED'
 if result is None:return 'NO_CANDIDATE_RESULT_UNRANKED'
 if result.get('complete') is not True:return 'PARTIAL_OR_FAILED_UNRANKED'
 return 'COMPLETE_QUALIFIED_ELIGIBLE' if result.get('qualified') is True else 'COMPLETE_SCIENTIFIC_NEGATIVE_UNRANKED'
def manifest_rows(obj):
 if not isinstance(obj,dict) or not any(k in obj for k in ['files','output_files']):raise ValueError('MANIFEST_FILES_FIELD_REQUIRED')
 rows=obj.get('files',obj.get('output_files'))
 if isinstance(rows,dict):
  for k,v in rows.items():yield k,v if isinstance(v,str) else v.get('sha256')
 elif isinstance(rows,list):
  for v in rows:
   if v.get('kind')=='symlink':continue
   yield v.get('path',v.get('relative_path')),v.get('sha256')
 else:raise ValueError('UNRECOGNIZED_MANIFEST_FILES_SCHEMA')
class Verifier:
 def __init__(self,package,index,strict=False,stage='preseal',self_identity=None,max_bytes=2**30):
  self.P=Path(package).resolve();self.index=index;self.strict=strict;self.stage=stage;self.me=self_identity or {};self.max_bytes=max_bytes;self.inputs={};self.cache={};self.issues=[];self.limits=[];self.observations={};self.delegated={}
 def issue(self,code,**kw):self.issues.append({'code':code,**kw})
 def path(self,relative):
  p=(self.P/relative).resolve()
  if not p.is_relative_to(self.P):raise ValueError('PACKAGE_INPUT_ESCAPE:'+str(relative))
  return p
 def sha(self,p):
  p=Path(p).resolve();s=p.stat();key=(str(p),s.st_size,s.st_mtime_ns)
  if key in self.cache:return self.cache[key]
  if not p.is_relative_to(self.P):raise ValueError('EXTERNAL_HISTORY_MUST_USE_MAIN_FINAL_HASH_REPORT')
  if s.st_size>self.max_bytes:raise ValueError('HASH_FILE_RESOURCE_LIMIT:'+str(p))
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(2**20),b''):h.update(b)
  if (p.stat().st_size,p.stat().st_mtime_ns)!=(s.st_size,s.st_mtime_ns):raise ValueError('INPUT_CHANGED_DURING_HASH')
  self.cache[key]=h.hexdigest();self.inputs[str(p.relative_to(self.P))]={'sha256':h.hexdigest(),'bytes':s.st_size};return h.hexdigest()
 def read(self,p):
  p=Path(p);self.sha(p)
  if p.stat().st_size>256*2**20:raise ValueError('JSON_RESOURCE_LIMIT')
  return json.loads(p.read_text())
 def check_digest(self,p,expected,context):
  if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):self.issue('INVALID_EXPECTED_DIGEST',context=context);return
  p=Path(p).resolve()
  if not p.is_relative_to(self.P):
   actual=self.delegated.get(str(p));
   if actual!=expected:self.issue('EXTERNAL_HISTORY_NOT_COVERED_BY_FINAL_HASH_REFERENCE',path=str(p),context=context)
   return
  if not p.is_file():self.issue('MISSING_HASHED_FILE',path=str(p),context=context);return
  if self.sha(p)!=expected:self.issue('DIGEST_MISMATCH',path=str(p),context=context)
 def reference(self,ref,name):
  if not isinstance(ref,dict) or not ref.get('path') or not ref.get('sha256') or not isinstance(ref.get('require'),dict) or not ref['require']:
   self.issue('MISSING_OR_UNASSERTED_FINAL_REFERENCE',reference=name);return None
  p=self.path(ref['path'])
  if not p.exists():self.issue('MISSING_FINAL_REFERENCE',reference=name,path=ref['path']);return None
  self.check_digest(p,ref['sha256'],name);d=self.read(p)
  for key,value in ref['require'].items():
   try:actual=pointer(d,key)
   except (KeyError,IndexError,TypeError,ValueError):self.issue('REFERENCE_FIELD_MISSING',reference=name,field=key);continue
   if actual!=value:self.issue('REFERENCE_ASSERTION_FAILED',reference=name,field=key,expected=value,actual=actual)
  return d
 def digest_map(self,m,base,context):
  for rel,h in m.items():self.check_digest(Path(rel) if Path(rel).is_absolute() else base/rel,h,context)
 def process_audit(self,d,context):
  ended=True
  for q in identities(d):
   if q==self.me:continue
   state=pid_state(q)
   if state in ['LIVE','ZOMBIE']:self.issue('OWNED_PROCESS_NOT_ENDED',context=context,process=q,state=state);ended=False
  return ended
 def preimport_zero_start(self,g,c,config_path,supervisor_end,raw_start_count,eng):
  """Only original HOLDSS01 NumPy import failure; never a generic no-START waiver."""
  before=len(self.issues);spec=eng.get('preimport_zero_start',{})
  def require(ok,why):
   if not ok:self.issue('PREIMPORT_ZERO_START_EVIDENCE_REJECTED',group=g,reason=why)
  require(g=='HOLDSS01' and spec.get('schema')=='ihear.holdss01.preimport_zero_start.v3' and spec.get('group')==g,'EXPLICIT_NARROW_SCHEMA')
  require(eng.get('zero_START') is True and raw_start_count==0,'NOT_EXACT_ZERO_START')
  require(spec.get('worker_source_manifest_absent_acknowledged') is True and spec.get('runtime_worker_source_identity_proven') is False,'SOURCE_IDENTITY_LIMITATION_REQUIRED')
  require(not (self.P/'jobs'/g/'SOURCE_MANIFEST.json').exists() and not (self.P/'jobs'/g/'WORKER_DONE.json').exists(),'UNEXPECTED_WORKER_MANIFEST_OR_DONE')
  if len(self.issues)!=before:return False
  names={'prelaunch':'audit/HOLDSS01_PRELAUNCH.json','binding':'audit/HOLDSS01_VALIDATION_BINDING.json','launch':'owned/HOLDSS01_DETACHED_LAUNCH.json','supervisor':'owned/HOLDSS01_SUPERVISOR.json','supervisor_end':'owned/HOLDSS01_SUPERVISOR_END.json','descendants':'owned/HOLDSS01_DESCENDANTS.json','freeze':'freeze/HOLDSS01.json'}
  docs={}
  for name,path in names.items():
   ref=spec.get(name,{})
   require(ref.get('path')==path,'ORIGINAL_EVIDENCE_PATH:'+name)
   d=self.reference(ref,'HOLDSS01_PREIMPORT:'+name)
   if isinstance(d,dict):docs[name]=d
   else:require(False,'MISSING_JSON:'+name)
  if len(self.issues)!=before:return False
  pre,bind,launch,sup,end,desc,fr=(docs[k] for k in names)
  config_sha=self.sha(config_path)
  require(c.get('group')==g and c.get('worker')=='v7_worker_v8.py','ORIGINAL_GROUP_AND_WORKER')
  for name,d in [('prelaunch',pre),('binding',bind),('launch',launch),('supervisor',sup),('freeze',fr)]:require(d.get('config_sha256')==config_sha,'CONFIG_BINDING:'+name)
  require(pre.get('status')=='PASS' and pre.get('group')==g and bind.get('status')=='PASS' and bind.get('group')==g and launch.get('group')==g and fr.get('group')==g,'ORIGINAL_PASS_GROUP_FIELDS')
  require(bind.get('exact_fields_and_canonical_config_verified') is True and bind.get('original_contract_unchanged') is True and pre.get('new_physics')==0 and bind.get('new_physics')==0,'ORIGINAL_PRELAUNCH_SEMANTIC_BINDING')
  require(end==supervisor_end and end.get('state')=='STOP' and end.get('worker_exit_code')==1 and end.get('survivors')==[] and end.get('reason')=='WORKER_FAILED_EVIDENCE_PRESERVED','ORIGINAL_FAILED_CLOSED_SUPERVISOR')
  def ident(d):return {k:d.get(k) for k in ['pid','start_ticks']} if isinstance(d,dict) else None
  worker=ident(sup.get('worker'));owner=ident(sup.get('identity'))
  require(worker is not None and all(type(v) is int for v in worker.values()) and owner is not None and all(type(v) is int for v in owner.values()),'PID_TICKS_REQUIRED')
  require(ident(launch.get('supervisor'))==owner,'LAUNCH_SUPERVISOR_IDENTITY')
  known=end.get('known_owned',{});desc_owned=desc.get('known_owned',{})
  require(worker is not None and ident(known.get(str(worker.get('pid'))))==worker and ident(desc_owned.get(str(worker.get('pid'))))==worker,'WORKER_END_DESCENDANT_IDENTITY')
  for name,d in docs.items():require(self.process_audit(d,'HOLDSS01_PREIMPORT:'+name),'OWNED_PROCESS_LIVE:'+name)
  try:require(fr['frozen_unix']<=pre['created_unix']<=bind['created_unix']<=launch['created_unix']<=sup['started_unix']==end['started_unix']<end['ended_unix'],'ORIGINAL_RECEIPT_TIME_ORDER')
  except (KeyError,TypeError):require(False,'TIME_FIELDS_MISSING')
  plan=spec.get('runtime_plan',{});require(plan.get('path')=='runtime/HOLDSS01_TEST_PLAN.json','RUNTIME_PLAN_PATH')
  if plan.get('path'):
   self.check_digest(self.path(plan['path']),plan.get('sha256'),'HOLDSS01_RUNTIME_PLAN')
   require(plan.get('sha256')==config_sha==pre.get('exact_runtime_plan_sha256')==bind.get('runtime_test_plan_sha256'),'EXACT_RUNTIME_PLAN_CONFIG')
  require(bind.get('prelaunch_sha256')==spec['prelaunch'].get('sha256') and bind.get('freeze_sha256')==spec['freeze'].get('sha256'),'PRELAUNCH_FREEZE_DIGEST_BINDING')
  require(c.get('holdout_protocol_sha256')==fr.get('holdout_protocol_sha256')==bind.get('protocol_sha256'),'FROZEN_PROTOCOL_BINDING')
  if c.get('holdout_protocol'):self.check_digest(self.path(c['holdout_protocol']),c.get('holdout_protocol_sha256'),'HOLDSS01_PROTOCOL')
  expected_sources={'source/v7_prepare_job.py':pre.get('source_sha256'),'source/v7_validate_holdout_binding_v1.py':bind.get('source_sha256'),'source/v7_launch_detached.py':launch.get('launcher_source_sha256'),'source/v7_supervise_v3.py':launch.get('supervisor_source_sha256'),'source/v7_worker_v8.py':c.get('frozen_artifacts',{}).get('source/v7_worker_v8.py')}
  require(spec.get('source_sha256')==expected_sources,'EXACT_ORIGINAL_SOURCE_BINDINGS')
  self.digest_map(expected_sources,self.P,'HOLDSS01_ORIGINAL_PREIMPORT_SOURCES')
  require(pre.get('frozen_artifacts')==c.get('frozen_artifacts')==fr.get('frozen_artifacts'),'ORIGINAL_FROZEN_ARTIFACT_INVENTORY')
  self.digest_map(c.get('frozen_artifacts',{}),self.P,'HOLDSS01_PRELAUNCH_FROZEN_ARTIFACTS')
  log=spec.get('worker_log',{});require(log.get('path')=='logs/HOLDSS01_worker.log','ORIGINAL_IMPORT_LOG_PATH')
  if log.get('path'):
   p=self.path(log['path']);self.check_digest(p,log.get('sha256'),'HOLDSS01_IMPORT_LOG')
   if p.exists():
    text=p.read_text();require(text.rstrip().endswith("ModuleNotFoundError: No module named 'numpy'"),'EXACT_NUMPY_IMPORT_FAILURE')
    for path,line in [('source/v7_worker_v8.py',8),('runtime/control/campaign_v6.py',7),('runtime/control/base_campaign.py',7),('runtime/code/study_common.py',11)]:require('File "'+str(self.P/path)+'", line '+str(line)+', in <module>' in text,'IMPORT_TRACE_PATH_LINE:'+path)
    require('    import numpy as np' in text and 'Traceback (most recent call last):' in text,'ORIGINAL_MODULE_IMPORT_TRACE')
  if len(self.issues)!=before:return False
  self.limits.append({'id':'HOLDSS01_PREIMPORT_NO_WORKER_SOURCE_MANIFEST','category':'ZERO_START_PREIMPORT_SOURCE_IDENTITY_LIMITED','message':'Original prelaunch/config/launcher/source hashes and failed import ownership are bound, but no worker-created SOURCE_MANIFEST or independent loaded-module identity exists. Do not claim complete runtime source identity.','evidence':spec['launch']['path'],'metadata_perfect_PASS_allowed':False})
  self.observations.setdefault('preimport_zero_start_engineering',[]).append({'group':g,'classification':'ZERO_START_PREIMPORT_ENGINEERING_FAILURE_UNRANKED','physical_START':0,'worker_SOURCE_MANIFEST':'ABSENT_ORIGINAL_NOT_FABRICATED','source_identity_scope':'PRELAUNCH_FROZEN_INVENTORY_AND_IMPORT_TRACE_ONLY','runtime_worker_source_identity_proven':False,'candidate_or_success_result_created':False})
  return True
 def devpc01_zero_start(self,g,c,config_path,supervisor_end,raw_start_count,eng):
  """Original DEVPC01 missing-plan import failure only; no generic waiver."""
  before=len(self.issues);spec=eng.get('devpc01_preimport_zero_start',{})
  def require(ok,why):
   if not ok:self.issue('DEVPC01_ZERO_START_EVIDENCE_REJECTED',group=g,reason=why)
  cfg='f83e3ed3637d1890536ea54a334bcda7bdc86070ceb7db6862341129aa3e29e3';worker_sha='788be3d7957bf20d14b36e51011579cf6c1720b7b829294853412e2f8812cffb';model_sha='a2ac6678017bb14a3224f423c6a0c142eb3211427ff82c0bbfbd05109d7a80b8'
  require(g=='DEVPC01' and spec.get('schema')=='ihear.devpc01.missing_plan_zero_start.v4' and spec.get('group')==g,'EXPLICIT_ORIGINAL_GROUP_SCHEMA')
  require(eng.get('zero_START') is True and raw_start_count==0,'NOT_EXACT_ZERO_START_GROUP')
  require(spec.get('original_absent_metadata_acknowledged') is True and spec.get('runtime_loaded_source_or_interpreter_identity_proven') is False,'METADATA_LIMITATION_REQUIRED')
  absent=['audit/DEVPC01_PRELAUNCH.json','owned/DEVPC01_DETACHED_LAUNCH.json','jobs/DEVPC01/SOURCE_MANIFEST.json','jobs/DEVPC01/WORKER_DONE.json','runtime/DEVPC01_TEST_PLAN.json']
  for rel in absent:require(not(self.P/rel).exists(),'ORIGINAL_ABSENT_PATH_CREATED:'+rel)
  if len(self.issues)!=before:return False
  refs={'freeze':'freeze/DEVPC01.json','supervisor':'owned/DEVPC01_SUPERVISOR.json','supervisor_end':'owned/DEVPC01_SUPERVISOR_END.json','descendants':'owned/DEVPC01_DESCENDANTS.json'};docs={}
  for name,path in refs.items():
   ref=spec.get(name,{});require(ref.get('path')==path,'ORIGINAL_EVIDENCE_PATH:'+name);d=self.reference(ref,'DEVPC01:'+name)
   if isinstance(d,dict):docs[name]=d
   else:require(False,'MISSING_EVIDENCE:'+name)
  if len(self.issues)!=before:return False
  fr,sup,end,desc=(docs[n] for n in refs)
  require(self.sha(config_path)==cfg==fr.get('config_sha256')==sup.get('config_sha256'),'EXACT_ORIGINAL_CONFIG_SHA')
  require(c.get('group')==g and c.get('worker')=='v7_worker_v5.py' and fr.get('group')==g and fr.get('worker_source_sha256')==worker_sha,'FROZEN_WORKER_IDENTITY')
  require(c.get('frozen_artifacts')==fr.get('frozen_artifacts') and fr.get('frozen_artifacts',{}).get('models/LOCAL_RESPONSE_2D_V1/MODEL.json')==model_sha,'FROZEN_MODEL_AND_ARTIFACT_IDENTITY')
  require(fr.get('quality_contract')=={'original_gates':'all unchanged','hip_knee_jerk_RMS_ratio_max_vs_V6PHASE':1.001,'force_norm_rate_RMS_ratio_max_vs_V6PHASE':1.004,'JF_delta_max':0.,'JM_delta_max':0.},'ORIGINAL_QUALITY_CONTRACT_CHANGED')
  self.check_digest(self.P/'source/v7_worker_v5.py',worker_sha,'DEVPC01_ORIGINAL_FROZEN_WORKER');self.digest_map(fr.get('frozen_artifacts',{}),self.P,'DEVPC01_ORIGINAL_FROZEN_ARTIFACTS')
  require(end==supervisor_end and end.get('state')=='STOP' and end.get('reason')=='WORKER_FAILED_EVIDENCE_PRESERVED' and end.get('worker_exit_code')==1 and end.get('survivors')==[],'FAILED_SUPERVISOR_CLOSURE')
  def ident(d):return {k:d.get(k) for k in ['pid','start_ticks']} if isinstance(d,dict) else None
  owner,worker=ident(sup.get('identity')),ident(sup.get('worker'))
  require(owner is not None and worker is not None and all(type(v) is int for d in [owner,worker] for v in d.values()),'OWNER_PID_TICKS')
  require(owner=={'pid':975818,'start_ticks':56284124} and worker=={'pid':975820,'start_ticks':56284131},'EXACT_ORIGINAL_OWNER_WORKER_PID_TICKS')
  require(worker is not None and ident(end.get('known_owned',{}).get(str(worker.get('pid'))))==worker and ident(desc.get('known_owned',{}).get(str(worker.get('pid'))))==worker,'MATCHING_WORKER_END_DESCENDANT')
  if owner and worker:require(sup.get('worker',{}).get('ppid')==owner['pid'],'WORKER_PARENT_IDENTITY')
  for name,d in docs.items():require(self.process_audit(d,'DEVPC01:'+name),'OWNED_PROCESS_NOT_ENDED:'+name)
  events={};decision_path=self.P/'RESEARCH_DECISIONS.jsonl'
  if not decision_path.exists():require(False,'ORIGINAL_DECISION_JOURNAL_MISSING')
  else:
   self.sha(decision_path)
   with decision_path.open() as f:
    for number,line in enumerate(f,1):
     if number in (31,34):
      expected=spec.get('decision_line_sha256',{}).get(str(number));require(hashlib.sha256(line.encode()).hexdigest()==expected,'ORIGINAL_DECISION_LINE_SHA:'+str(number))
      try:events[number]=json.loads(line)
      except ValueError:require(False,'DECISION_LINE_JSON:'+str(number))
     if number>=34:break
  reg,rec=events.get(31,{}),events.get(34,{})
  require(reg.get('event')=='MAJOR_MODEL_AND_DISPATCH_DECISION' and reg.get('next_group')==g and reg.get('config_sha256')==cfg and reg.get('model_sha256')==model_sha,'ORIGINAL_PREDISPATCH_REGISTRATION')
  require(rec.get('event')=='ENGINEERING_RECOVERY_REGISTERED' and rec.get('failed_group')==g and rec.get('new_group')=='DEVPC02' and rec.get('no_physical_START_in_failed_group') is True and rec.get('scientific_actions_unchanged') is True and rec.get('source_worker_unchanged') is True and rec.get('budget_and_deadline_unchanged') is True,'ORIGINAL_ZERO_START_RECOVERY')
  try:require(fr['frozen_unix']<=reg['unix']<=sup['started_unix']==end['started_unix']<end['ended_unix']<=rec['unix'],'ORIGINAL_TIME_ORDER')
  except (KeyError,TypeError):require(False,'MISSING_TIME_FIELDS')
  log=spec.get('worker_log',{});require(log.get('path')=='logs/DEVPC01_worker.log','ORIGINAL_IMPORT_LOG_PATH')
  if log.get('path'):
   p=self.path(log['path']);self.check_digest(p,log.get('sha256'),'DEVPC01_MISSING_PLAN_LOG')
   if p.exists():
    text=p.read_text();require(text.rstrip().endswith("FileNotFoundError: [Errno 2] No such file or directory: '"+str(self.P/'runtime/DEVPC01_TEST_PLAN.json')+"'"),'EXACT_MISSING_PLAN_ERROR')
    for path,line in [('source/v7_worker_v5.py',8),('runtime/control/campaign_v6.py',18)]:require('File "'+str(self.P/path)+'", line '+str(line)+', in <module>' in text,'EXACT_IMPORT_FRAME:'+path)
    require('Traceback (most recent call last):' in text and "CONFIG=json.loads((P/(GROUP+'_TEST_PLAN.json')).read_text())" in text,'ORIGINAL_MISSING_PLAN_IMPORT_SITE')
  current=spec.get('current_import_source_review',{});require(current.get('path')=='runtime/control/campaign_v6.py' and current.get('original_load_attestation') is False,'CURRENT_SOURCE_NOT_ORIGINAL_LOAD_ATTESTATION')
  if current.get('path'):self.check_digest(self.path(current['path']),current.get('sha256'),'DEVPC01_CURRENT_IMPORT_SOURCE_REVIEW_ONLY')
  if len(self.issues)!=before:return False
  self.limits.append({'id':'DEVPC01_ZERO_START_MISSING_PLAN_NO_RUNTIME_MANIFEST','category':'ZERO_START_DEVPC01_RUNTIME_IDENTITY_LIMITED','message':'Original frozen config/worker/model, owner and missing-plan traceback are bound. PRELAUNCH, launcher, runtime plan and worker SOURCE_MANIFEST were absent. Current campaign source is review-only; complete loaded-runtime/interpreter identity is not proven.','evidence':spec['supervisor_end']['path'],'metadata_perfect_PASS_allowed':False})
  self.observations.setdefault('preimport_zero_start_engineering',[]).append({'group':g,'classification':'ZERO_START_MISSING_PLAN_ENGINEERING_FAILURE_UNRANKED','physical_START':0,'runtime_plan_and_worker_SOURCE_MANIFEST':'ABSENT_ORIGINAL_NOT_FABRICATED','runtime_loaded_source_or_interpreter_identity_proven':False,'candidate_or_success_result_created':False})
  return True
 def run(self):
  # Final references are small reports only. Never walk/hash historical roots.
  refs=self.index.get('final_references',{})
  for name in ['historical_content','protected_inputs','journal_prefix','attempt_accounting','owned_final']:
   if self.strict or name in refs:
    d=self.reference(refs.get(name),name)
    if name=='historical_content' and d:
     if d.get('status')!='PASS' or d.get('errors') or d.get('checked_files')!=d.get('expected_files'):self.issue('HISTORICAL_FINAL_NOT_COMPLETE')
     for rel,h in d.get('files',{}).items():self.delegated[str((self.P.parent/rel).resolve())]=h
  for lim in self.index.get('known_limitations',[]):
   if self.reference(lim,'known_limitation:'+str(lim.get('id'))):self.limits.append({'id':lim.get('id'),'category':lim.get('category'),'message':lim.get('message'),'evidence':lim.get('path'),'metadata_perfect_PASS_allowed':False})
  if self.strict and not any(x.get('category')=='FOREGROUND_STATIC_TOOL_EXIT_ONLY' for x in self.limits):self.issue('REGISTERED_FOREGROUND_METADATA_LIMITATIONS_NOT_DECLARED')
  for ref in self.index.get('freeze_refs',[]):self.reference(ref,'SCIENTIFIC_FREEZE')
  if self.strict and not self.index.get('freeze_refs'):self.issue('SCIENTIFIC_FREEZE_REFERENCE_INVENTORY_MISSING')
  pending=[]
  for name in REQUIRED:
   p=self.P/name
   if not p.exists():
    if self.stage=='preseal' and name in PRESEAL_PENDING:pending.append(name)
    else:self.issue('REQUIRED_DELIVERABLE_MISSING',path=name)
   elif p.is_file():self.sha(p)
  self.observations['preseal_pending']=pending;self.observations['required_deliverables_exact_count']=len(REQUIRED)
  for name in [x for x in REQUIRED if x.endswith('.md')]:
   p=self.P/name
   if not p.exists():continue
   for link in re.findall(r'(?<!!)\[[^\]]*\]\(([^)]+)\)',p.read_text()):
    link=link.strip('<>')
    if re.match(r'^[a-zA-Z]+://',link) or link.startswith('#'):continue
    target=link.split('#')[0];target=re.sub(r':\d+$','',target)
    if target and not (p.parent/target).exists() and not allowed_pending_report_link(self.P,p,target,self.stage):self.issue('BROKEN_LOCAL_REPORT_LINK',report=name,target=link)
  ledger=self.P/'runtime/ATTEMPTS.jsonl';rawrows=[]
  if not ledger.exists():self.issue('RUNTIME_LEDGER_MISSING')
  else:
   self.sha(ledger)
   for n,line in enumerate(ledger.read_text().splitlines()):
    try:rawrows.append(json.loads(line))
    except ValueError:self.issue('MALFORMED_LEDGER_LINE',line=n+1)
  joins,errors=join_ledger(rawrows);self.issues+=errors;self.observations['physical_START']=sum(r.get('event')=='START' for r in rawrows);self.observations['physical_END']=sum(r.get('event')=='END' for r in rawrows)
  groups=collections.defaultdict(list)
  for row in joins:
   if not isinstance(row['group'],str):self.issue('START_GROUP_MISSING',id=row['id'])
   groups[row['group']].append(row)
  closed={};configs={};engineering=self.index.get('engineering_failures',{});aliases=self.index.get('raw_aliases',{})
  for f in sorted((self.P/'experiments').glob('*.json')):
   c=self.read(f)
   if not isinstance(c,dict) or not isinstance(c.get('group'),str):continue
   g=c['group'];supervisor=self.P/'owned'/(g+'_SUPERVISOR_END.json');started=(self.P/'owned'/(g+'_SUPERVISOR.json')).exists() or g in groups
   selected=self.index.get('config_paths',{}).get(g)
   if selected and f.resolve()!=self.path(selected):continue
   if not selected and (self.P/'experiments'/(g+'.json')).exists() and f.name!=g+'.json':continue
   if not started:continue
   if g in configs:self.issue('AMBIGUOUS_EXECUTED_CONFIG_PATH',group=g);continue
   configs[g]=(f,c)
   if not supervisor.exists():self.issue('JOB_NOT_CLOSED_NO_SUPERVISOR_END',group=g);closed[g]=False;continue
   s=self.read(supervisor);ended=self.process_audit(s,str(supervisor));closed[g]=ended and s.get('state')=='STOP' and s.get('survivors')==[]
   if not closed[g]:self.issue('SUPERVISOR_NOT_CLOSED',group=g);continue
   eng=g in engineering
   if eng:self.reference(engineering[g]['evidence'],'engineering:'+g)
   if s.get('worker_exit_code')!=0 and not eng:self.issue('NONZERO_JOB_NOT_CLASSIFIED_ENGINEERING_OR_SCIENTIFIC_FAILURE',group=g)
   raw_start_count=sum(r.get('event')=='START' and r.get('group')==g for r in rawrows)
   preimport_ok=self.preimport_zero_start(g,c,f,s,raw_start_count,engineering[g]) if engineering.get(g,{}).get('preimport_zero_start') or (g=='HOLDSS01' and eng) else False
   devpc01_ok=self.devpc01_zero_start(g,c,f,s,raw_start_count,engineering[g]) if engineering.get(g,{}).get('devpc01_preimport_zero_start') or (g=='DEVPC01' and eng) else False
   count=len(groups[g]);wd=self.P/'jobs'/g/'WORKER_DONE.json'
   if engineering.get(g,{}).get('zero_START') is True and count!=0:self.issue('ZERO_START_DECLARATION_CONFLICT',group=g)
   if count==0:
    if not eng:self.issue('STARTED_JOB_ZERO_START_UNEXPLAINED',group=g)
    sm=self.P/'jobs'/g/'SOURCE_MANIFEST.json'
    if sm.exists():
     m=self.read(sm);self.digest_map(dict(manifest_rows(m)),self.P,'ZERO_START_SOURCE_MANIFEST:'+g)
     if m.get('config_sha256')!=self.sha(f):self.issue('JOB_CONFIG_SHA_MISMATCH',group=g)
    elif not (preimport_ok or devpc01_ok):self.issue('ZERO_START_SOURCE_MANIFEST_MISSING',group=g)
    continue
   if wd.exists():
    w=self.read(wd);self.process_audit(w,str(wd))
    if w.get('all_children_joined') is not True:self.issue('CHILDREN_NOT_JOINED',group=g)
    for row in w.get('parent_checks',[]):
     if row.get('unchanged') is not True or row.get('before')!=row.get('after'):self.issue('FORK_PARENT_IDENTITY_FAILURE',group=g,id=row.get('id'))
   elif not eng:self.issue('WORKER_DONE_MISSING',group=g)
   sm=self.P/'jobs'/g/'SOURCE_MANIFEST.json'
   if not sm.exists():self.issue('JOB_SOURCE_MANIFEST_MISSING',group=g);continue
   m=self.read(sm);self.digest_map(dict(manifest_rows(m)),self.P,'SOURCE_MANIFEST:'+g)
   if m.get('config_sha256')!=self.sha(f):self.issue('JOB_CONFIG_SHA_MISMATCH',group=g)
   test=self.P/'runtime'/(g+'_TEST_PLAN.json')
   if test.exists() and self.sha(test)!=self.sha(f):self.issue('RUNTIME_PLAN_NOT_EXACT_CONFIG',group=g)
   if c.get('condition',{}).get('name')!=g:
    if not eng:self.issue('CONDITION_NAME_GROUP_MISMATCH',group=g)
    else:self.observations.setdefault('engineering_name_mismatches',[]).append({'group':g,'condition_name':c.get('condition',{}).get('name'),'all_results_unranked':True})
   for rel,h in c.get('frozen_artifacts',{}).items():self.check_digest(self.path(rel),h,'CONFIG_FROZEN_ARTIFACT:'+g)
   if c.get('case_path'):self.check_digest(self.path(c['case_path']),c.get('case_sha256'),'CASE:'+g)
   if c.get('holdout_protocol'):self.check_digest(self.path(c['holdout_protocol']),c.get('holdout_protocol_sha256'),'HOLDOUT_PROTOCOL:'+g)
   freeze=self.P/'freeze'/(g+'.json')
   if freeze.exists():
    fr=self.read(freeze)
    for rel,h in fr.get('frozen_artifacts',{}).items():self.check_digest(self.path(rel),h,'FREEZE:'+g)
   for attempt in groups[g]:
    if attempt['START'].get('config_sha256') not in (None,self.sha(f)):self.issue('START_CONFIG_SHA_MISMATCH',id=attempt['id'])
    if attempt['START'].get('job_source_sha256') not in (None,self.sha(sm)):self.issue('START_SOURCE_MANIFEST_SHA_MISMATCH',id=attempt['id'])
  attempts=[]
  for row in joins:
   ident,g=row['id'],row['group']
   if not closed.get(g):continue # Never read any active job's outcome/raw metadata.
   eng=g in engineering;rf=self.P/'attempts'/(ident+'_RESULT.json');r=self.read(rf) if rf.exists() else None;rawid=ident
   if ident in aliases:
    a=aliases[ident];self.reference(a['evidence'],'raw_alias:'+ident);rawid=a['raw_id']
    if not eng or a.get('unranked') is not True:self.issue('RAW_ALIAS_NOT_ENGINEERING_UNRANKED',id=ident)
    for name,h in a.get('sha256',{}).items():self.check_digest(self.P/'runtime/source/results'/rawid/name,h,'ENGINEERING_RAW_ALIAS:'+ident)
   raw=self.P/'runtime/source/results'/rawid;summary=raw/'summary.json'
   if r:
    if r.get('id')!=ident:self.issue('RESULT_ID_MISMATCH',id=ident)
    if r.get('qualified') is True and r.get('complete') is not True:self.issue('PARTIAL_MARKED_QUALIFIED',id=ident)
    if eng and (r.get('qualified') or r.get('successful_cost_rank_eligible')):self.issue('ENGINEERING_FAILURE_RANKED_AS_SUCCESS',id=ident)
    if r.get('complete'):
     for name in ['trace.npz','summary.json','runtime_artifacts.json.gz']:
      if not (raw/name).is_file():self.issue('COMPLETE_RESULT_RAW_MISSING',id=ident,file=name)
     if summary.exists() and self.read(summary).get('status')!='COMPLETE':self.issue('COMPLETE_RESULT_SUMMARY_NOT_COMPLETE',id=ident)
   elif row['START'].get('kind')!='LEGAL_COLD_PARENT' and not ident.endswith('_parent') and not eng:self.issue('CANDIDATE_RESULT_MISSING',id=ident)
   state=classify(r,eng);replay=self.P/'audit/scorer_replay'/(ident+'.json')
   if r and r.get('complete'):
    if not replay.exists():self.issue('COMPLETE_RESULT_SCORER_REPLAY_MISSING',id=ident)
    else:
     q=self.read(replay)
     if q.get('status')!='SCORER_REPLAY_PASS' or q.get('original_result_exact_reproduced') is not True:self.issue('SCORER_REPLAY_EVIDENCE_MISMATCH',id=ident,status=q.get('status'))
     if q.get('qualified_replay')!=r.get('qualified'):self.issue('SCORER_FALSE_QUALIFICATION_NOT_PRESERVED',id=ident)
     for rel,h in q.get('input_sha256',{}).items():self.check_digest(self.path(rel),h,'SCORER_RAW:'+ident)
   metrics=self.P/'analysis/native_metrics'/(ident+'.json')
   if metrics.exists():
    m=self.read(metrics)
    for name,h in m.get('source_hashes',{}).items():self.check_digest(raw/name,h,'NATIVE_METRIC_RAW:'+ident)
    if r and m.get('qualified_original')!=r.get('qualified'):self.issue('NATIVE_METRIC_QUALIFICATION_MISMATCH',id=ident)
   attempts.append({'id':ident,'group_from_unique_START':g,'raw_id':rawid,'classification':state,'complete':r.get('complete') if r else None,'qualified':r.get('qualified') if r else None,'successful_cost_rank_eligible':state=='COMPLETE_QUALIFIED_ELIGIBLE','END_returncode':row['END'].get('returncode'),'END_native_steps':row['END'].get('native_steps'),'unknown_native_steps_is_not_zero':row['END'].get('native_steps') is None})
  self.observations['attempts']=attempts
  self.observations['wall_CPU_accounting']='No sum of nested inclusive wall/CPU. START/END/native counts are disjoint only when source says so; main accounting reference remains authoritative.'
  # Explicit model/data inventory; future invocation can add inventories without
  # guessing checkpoints from names or opening historical file trees.
  artifacts=self.index.get('artifact_sha256',{});self.digest_map(artifacts,self.P,'MODEL_DATA_INVENTORY')
  for folder in ['models','data']:
   for f in (self.P/folder).rglob('*') if (self.P/folder).exists() else []:
    if f.is_file() and str(f.relative_to(self.P)) not in artifacts:self.issue('MODEL_DATA_NOT_IN_FROZEN_INVENTORY',path=str(f.relative_to(self.P)))
  # Read ownership metadata, not scientific raw; no process is killed/repaired.
  for f in sorted((self.P/'owned').glob('*.json')):
   try:self.process_audit(self.read(f),str(f.relative_to(self.P)))
   except (ValueError,KeyError) as e:self.issue('OWNED_METADATA_UNREADABLE',path=str(f),error=str(e))
  for pair in self.index.get('owned_end_pairs',[]):
   for k in ['start','end']:
    if not self.path(pair[k]).is_file():self.issue('OWNED_START_END_RECORD_MISSING',path=pair[k])
   if all(self.path(pair[k]).is_file() for k in ['start','end']):
    a,b=(self.read(self.path(pair[k])) for k in ['start','end'])
    ai={tuple(sorted(q.items())) for q in identities(a)};bi={tuple(sorted(q.items())) for q in identities(b)}
    if not ai or not ai.intersection(bi):self.issue('OWNED_START_END_IDENTITY_NOT_BOUND',start=pair['start'],end=pair['end'])
    self.process_audit(a,pair['start']);self.process_audit(b,pair['end'])
  if self.strict and not self.index.get('owned_end_pairs'):self.issue('REGISTERED_TASK_PID_END_INVENTORY_MISSING')
  review_index=self.index.get('agent_reviews',[])
  if self.strict and not review_index:self.issue('AGENT_REVIEW_INVENTORY_REQUIRED')
  listed={r['directory'] for r in review_index}
  for d in (self.P/'agent_reviews').iterdir() if (self.P/'agent_reviews').exists() else []:
   if d.is_dir() and str(d.relative_to(self.P)) not in listed:self.issue('AGENT_REVIEW_NOT_IN_FINAL_INVENTORY',directory=str(d.relative_to(self.P)))
  for review in review_index:
   directory=self.path(review['directory']);ep=self.path(review['end']);mp=self.path(review['manifest'])
   if not ep.exists() or not mp.exists():self.issue('AGENT_REVIEW_END_OR_MANIFEST_MISSING',directory=review['directory']);continue
   e=self.read(ep);self.process_audit(e,review['end']);m=self.read(mp)
   digest_fields=[e.get(k) for k in ['manifest_sha256','output_manifest_sha256','output_manifest_SHA256'] if e.get(k)]
   if digest_fields and self.sha(mp) not in digest_fields:self.issue('REVIEW_END_MANIFEST_HASH_MISMATCH',directory=review['directory'])
   for rel,h in manifest_rows(m):
    if h:self.check_digest(Path(rel) if Path(rel).is_absolute() else directory/rel,h,'REVIEW_OUTPUT:'+review['directory'])
   if e.get('first_failed_AST_PID_metadata_gap_explicit') or e.get('first_failed_AST_PID_metadata_gap'):
    if not any(x.get('category')=='FOREGROUND_STATIC_TOOL_EXIT_ONLY' for x in self.limits):self.issue('KNOWN_FOREGROUND_PID_GAP_NOT_DECLARED')
  for ref in self.index.get('package_manifests',[]):
   m=self.reference(ref,'package_manifest')
   if m:
    for rel,h in manifest_rows(m):
     if rel in PRESEAL_PENDING and self.stage=='preseal':continue
     if h:self.check_digest(Path(rel) if Path(rel).is_absolute() else self.P/rel,h,'PACKAGE_MANIFEST')
  if self.strict and not self.index.get('package_manifests'):self.issue('FINAL_PACKAGE_MANIFEST_REFERENCE_MISSING')
  return {'schema':'ihear.final_verifier.v1','status':'INCOMPLETE' if self.issues else 'COMPLETE_WITH_DOCUMENTED_METADATA_LIMITATIONS' if self.limits else 'COMPLETE_PRESEAL' if self.stage=='preseal' else 'COMPLETE','metadata_integrity':'DOCUMENTED_PARTIAL_PREIMPORT_SOURCE_IDENTITY' if any(x.get('category') in ('ZERO_START_PREIMPORT_SOURCE_IDENTITY_LIMITED','ZERO_START_DEVPC01_RUNTIME_IDENTITY_LIMITED') for x in self.limits) else 'DOCUMENTED_PARTIAL_FOREGROUND_METADATA' if self.limits else 'NO_UNDECLARED_GAPS_IN_CHECKED_SCOPE','issues':self.issues,'known_limitations':self.limits,'observations':self.observations,'input_sha256':self.inputs,'mode':'strict-final' if self.strict else 'draft','stage':self.stage,'scientific_negative_is_package_damage':False,'all_scientific_methods_qualified':False,'new_env_model_train_physics':0,'verification_scope':'Referenced/indexed evidence and declared inventories; no score recomputation or universal safety proof'}
def cli():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--evidence-index',type=Path,required=True);ap.add_argument('--mode',choices=['draft','strict-final'],default='draft');ap.add_argument('--stage',choices=['preseal','sealed'],default='preseal');args=ap.parse_args()
 P=args.package.resolve();O=args.out.resolve();assert O.is_relative_to(P) and O!=P;O.mkdir(parents=True,exist_ok=False);began=time.time();me=identity()
 def put(name,d):
  p=O/name;p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 put('START.json',{'process':me,'unix':began,'mode':args.mode,'stage':args.stage,'before_any_input_hash':True})
 result={'status':'INCOMPLETE','error':'NOT_STARTED'}
 try:
  os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(768*2**20,768*2**20));resource.setrlimit(resource.RLIMIT_CPU,(900,910));signal.alarm(1000)
  source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();idx=args.evidence_index.resolve();assert idx.is_relative_to(P);index_bytes=idx.read_bytes();index_sha=hashlib.sha256(index_bytes).hexdigest()
  put('FROZEN_INPUT.json',{'source_sha256':source_sha,'evidence_index_path':str(idx),'evidence_index_sha256':index_sha})
  index=json.loads(index_bytes);v=Verifier(P,index,args.mode=='strict-final',args.stage,me);result=v.run()
  if hashlib.sha256(idx.read_bytes()).hexdigest()!=index_sha or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=source_sha:result['status']='INCOMPLETE';result.setdefault('issues',[]).append({'code':'VERIFIER_SOURCE_OR_INDEX_CHANGED'})
  put('VERIFICATION.json',result)
 except BaseException as e:result={'status':'INCOMPLETE','error':str(e),'traceback':traceback.format_exc(),'all_partial_outputs_retained':True};put('VERIFICATION.json',result)
 finally:
  signal.alarm(0);manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file()};put('OUTPUT_MANIFEST.json',{'files':manifest});put('END.json',{'status':result['status'],'process':me,'wall_s':time.time()-began,'manifest_sha256':hashlib.sha256((O/'OUTPUT_MANIFEST.json').read_bytes()).hexdigest(),'new_env_model_train_physics':0,'children':[]})
 print(json.dumps({'status':result['status'],'out':str(O)}));return 2 if result['status']=='INCOMPLETE' else 0
if __name__=='__main__':raise SystemExit(cli())
