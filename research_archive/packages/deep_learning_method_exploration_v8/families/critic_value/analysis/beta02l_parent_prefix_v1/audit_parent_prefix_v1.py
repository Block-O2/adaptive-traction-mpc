"""主审批准的60s单CPU只读审计；仅L原raw/源码/事件，不初始化模型。"""
from pathlib import Path
import ast
import gzip
import hashlib
import json
import os
import resource
import signal
import sys
import time


def array_items(path,key):
 with gzip.open(path,'rt') as f:
  buf='';needle='"'+key+'":';found=False;decoder=json.JSONDecoder()
  while not found:
   part=f.read(65536)
   if not part:return
   buf+=part;pos=buf.find(needle)
   if pos>=0:
    buf=buf[pos+len(needle):].lstrip()
    while not buf:buf+=f.read(65536);buf=buf.lstrip()
    if not buf.startswith('['):raise ValueError('NOT_ARRAY:'+key)
    buf=buf[1:];found=True
   else:buf=buf[-len(needle):]
  while True:
   buf=buf.lstrip(', \n\r\t')
   if buf.startswith(']'):return
   try:value,end=decoder.raw_decode(buf)
   except json.JSONDecodeError:
    part=f.read(65536)
    if not part:raise ValueError('INCOMPLETE_ARRAY:'+key)
    buf+=part
    if len(buf)>4*2**20:raise ValueError('ITEM_EXCEEDS_BOUNDED_EXTRACTION:'+key)
    continue
   yield value;buf=buf[end:]


def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while True:
   part=f.read(1024*1024)
   if not part:break
   h.update(part)
 return h.hexdigest()


def canonical(d):return json.dumps(d,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def load(p):return json.loads(Path(p).read_text())
def usage():
 r=resource.getrusage(resource.RUSAGE_SELF)
 return {'unix':time.time(),'PID':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'CPU_user_s':r.ru_utime,'CPU_system_s':r.ru_stime,'RSS_peak_KiB':r.ru_maxrss,'affinity':sorted(os.sched_getaffinity(0)),'python':sys.executable,'binary_sha256':sha(Path(sys.executable).resolve())}
def save(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def compare(parent, baseline, key):
 gp=array_items(parent,key);gb=array_items(baseline,key);hp=hashlib.sha256();hb=hashlib.sha256();hall=hashlib.sha256()
 count=0;bn=0;first=None;last=None;bf=None;bl=None;bad=None;prev=None;gaps=0;applied_sum=0;applied_unknown=0;positive=0
 sentinel=object()
 for p in gp:
  b=next(gb,sentinel);count+=1;first=p if first is None else first;last=p
  pc=canonical(p);hp.update(pc+b'\n')
  if b is sentinel:
   if bad is None:bad={'row0':count-1,'reason':'B_SHORTER_THAN_PARENT'}
  else:
   bc=canonical(b);hb.update(bc+b'\n');hall.update(bc+b'\n');bn+=1;bf=b if bf is None else bf;bl=b
   if pc!=bc and bad is None:bad={'row0':count-1,'reason':'FULL_RECORD_CANONICAL_MISMATCH','different_keys':[k for k in set(p)|set(b) if p.get(k)!=b.get(k)]}
  if key=='native_states_evaluation_only':
   now=p.get('native_step_index')
   if prev is not None and (not isinstance(now,(int,float)) or now-prev!=1):gaps+=1
   prev=now
  elif p.get('applied') is True:
   value=p.get('native_steps')
   if isinstance(value,(int,float)) and not isinstance(value,bool):applied_sum+=value;positive+=value>0
   else:applied_unknown+=1
 for b in gb:
  bn+=1;bf=b if bf is None else bf;bl=b;hall.update(canonical(b)+b'\n')
 def summary(row):
  if row is None:return None
  return {k:row.get(k) for k in (['native_step_index','time_s','command_id'] if key=='native_states_evaluation_only' else ['receipt_index','applied','start_physics_s','end_physics_s','native_steps'])}
 return {'key':key,'parent_count':count,'B_total_count':bn,'B_suffix_row_count':bn-count if bn>=count else None,
  'parent_nonempty':count>0,'prefix_full_record_exact':None if count==0 else bad is None,'first_mismatch':bad,
  'parent_canonical_stream_sha256':hp.hexdigest(),'B_matching_prefix_canonical_stream_sha256':hb.hexdigest(),'B_all_canonical_stream_sha256':hall.hexdigest(),
  'parent_first':summary(first),'parent_last':summary(last),'B_first':summary(bf),'B_last':summary(bl),'native_counter_nonunit_gaps':gaps if key=='native_states_evaluation_only' else None,
  'parent_applied_native_steps_sum':applied_sum if key=='command_receipts' and applied_unknown==0 and count>0 else None,
  'parent_applied_native_steps_unknown_fields':applied_unknown if key=='command_receipts' else None,'parent_positive_applied_receipts':positive if key=='command_receipts' else None,
  'full_parent_record_field_names':sorted(first) if first is not None else None}


def main():
 P=Path(__file__).resolve().parents[4];out=Path(__file__).resolve().parent/'run_once_v1'
 assert P.name=='deep_learning_method_exploration_v8' and not out.exists()
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(60,61))
 initial=usage();out.mkdir();save(out/'START.json',initial)
 def timeout(*_):raise TimeoutError('READ_ONLY_AUDIT_ORIGINAL_60S_STOP')
 signal.signal(signal.SIGTERM,timeout);signal.signal(signal.SIGALRM,timeout);signal.signal(signal.SIGXCPU,timeout);signal.setitimer(signal.ITIMER_REAL,59.5)
 result={'status':'STARTED','model_init_forward_fit_physics':0,'only_closed_L_owner_required_global_may_have_other_active_jobs':True}
 try:
  helper=P/'runtime/code/stream_runtime_evidence.py'
  original=next(n for n in ast.parse(helper.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='array_items')
  copied=next(n for n in ast.parse(Path(__file__).read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='array_items')
  assert ast.dump(original,include_attributes=False)==ast.dump(copied,include_attributes=False)
  result['original_array_reader_body_exact_AST']=True
  rawparent=P/'runtime/source/results/V8BETA02L_parent/runtime_artifacts.json.gz';rawB=P/'runtime/source/results/V8BETA02L_B/runtime_artifacts.json.gz'
  references=['experiments/V8BETA02L.json','jobs/V8BETA02L/SOURCE_MANIFEST.json','audit/V8BETA02L_FORK_CONTEXT.json','runtime/reports/V8BETA02L_PARENT_CHECKS.json','runtime/reports/V8BETA02L_B_SNAPSHOT.json','runtime/reports/V8BETA02L_OP_BETA_RF_RAW_01_SNAPSHOT.json','attempts/V8BETA02L_B_RESULT.json','attempts/V8BETA02L_OP_BETA_RF_RAW_01_RESULT.json','runtime/output/V8BETA02L_B_DATA.json','runtime/output/V8BETA02L_parent_PARTIAL_COMPUTE.json','audit/scorer_replay/V8BETA02L_B.json','audit/scorer_replay/V8BETA02L_parent.json','owned/V8BETA02L_SUPERVISOR_END.json','owned/V8BETA02L_EXIT.json','jobs/V8BETA02L/WORKER_DONE.json','audit/V8BETA02L_parent_ERROR.json','source/v8_worker_v2.py','runtime/code/stream_runtime_evidence.py','runtime/code/matched_harness.py','runtime/code/study_common.py','families/ppo_reward/continuous_scale_v1/beta_sampling_sequence_candidate_v1.py']
  result['references_sha256']={r:sha(P/r) if (P/r).is_file() else None for r in references}
  result['raw_compressed_sha256']={str(x.relative_to(P)):sha(x) for x in [rawparent,rawB]}
  manifest=load(P/'jobs/V8BETA02L/SOURCE_MANIFEST.json')
  sources={r:h for r,h in manifest['files'].items() if r in references or ('scor' in r.lower() and r.endswith('.py'))}
  result['original_job_source_bindings']={r:{'original_SHA':h,'actual_SHA':sha(P/r) if (P/r).is_file() else None} for r,h in sources.items()}
  result['native']=compare(rawparent,rawB,'native_states_evaluation_only')
  result['receipts']=compare(rawparent,rawB,'command_receipts')
  nd=result['native'];rd=result['receipts']
  fork=load(P/'audit/V8BETA02L_FORK_CONTEXT.json');ph=fork['full_manifest']['hash'];checks=load(P/'runtime/reports/V8BETA02L_PARENT_CHECKS.json')
  result['fork']={'physical_s':fork['physical_s'],'task_s':fork['task_s'],'parent_hash':fork['parent_hash'],'full_manifest_hash':ph,'full_manifest_file_sha256':sha(P/'audit/V8BETA02L_FORK_CONTEXT.json'),'parent_checks':checks,'snapshot_hashes':{x:load(P/('runtime/reports/'+x+'_SNAPSHOT.json'))['hash'] for x in ['V8BETA02L_B','V8BETA02L_OP_BETA_RF_RAW_01']}}
  ledger=P/'runtime/ATTEMPTS.jsonl';events=[]
  with ledger.open('rb') as f:
   for number,line in enumerate(f,1):
    if b'V8BETA02L_' not in line:continue
    row=json.loads(line)
    if row.get('id','').startswith('V8BETA02L_'):events.append({'line1':number,'rawline_sha256':hashlib.sha256(line).hexdigest(),'canonical_record_sha256':hashlib.sha256(canonical(row)).hexdigest(),'record':row})
  result['original_L_events']={'ledger_path':str(ledger.relative_to(P)),'events':events,'other_active_job_rows_not_parsed':True}
  hard=['force','moment','torque','human_speed','human_acceleration','robot_speed','session_clearance','true_clearance','measured_sleeve_clearance','no_shank_table_contact','no_human_rom_violation']
  metric=load(P/'runtime/output/V8BETA02L_B_DATA.json')['metric'];u=metric['physical_audit']['unchanged_evaluator'];original=u['physical_task_result']['scorer_v2_common_conditions'];replay=load(P/'audit/scorer_replay/V8BETA02L_B.json')
  result['B_original_11_hard']={k:original.get(k) for k in hard};result['B_original_mode_physical_result']={'mode':u['overall_result_for_mode'],'physical':u['physical_task_result']['status'],'replay_original_exact':replay.get('original_result_exact_reproduced'),'qualified_replay':replay.get('qualified_replay')}
  partial=load(P/'runtime/output/V8BETA02L_parent_PARTIAL_COMPUTE.json')
  result['parent_native_accounting']={'partial_compute_actual_new_native':partial.get('actual_new_native_physics_steps'),'raw_native_last_counter':nd['parent_last']['native_step_index'] if nd['parent_last'] else None,'raw_native_first_counter':nd['parent_first']['native_step_index'] if nd['parent_first'] else None,'raw_parent_positive_receipt_sum':rd['parent_applied_native_steps_sum'],'fork_physical_s':fork['physical_s'],'parent_final_raw_physical_s':nd['parent_last']['time_s'] if nd['parent_last'] else None,'B_total_minus_parent_counter':nd['B_last']['native_step_index']-nd['parent_last']['native_step_index'] if nd['B_last'] and nd['parent_last'] else None,'B_reported_new_native':load(P/'attempts/V8BETA02L_B_RESULT.json')['actual_new_native_steps'],'parent_END_native_absent_is_not_zero':True}
  closed=load(P/'owned/V8BETA02L_SUPERVISOR_END.json');closures=[]
  for pid,record in closed['known_owned'].items():
   p=Path('/proc')/pid/'stat';now=int(p.read_text().rsplit(')',1)[1].split()[19]) if p.exists() else None
   closures.append({'pid':int(pid),'original_start_ticks':record['start_ticks'],'now_start_ticks':now,'original_closed':now is None or now!=record['start_ticks']})
  result['closed_L_owner']={'state':closed['state'],'exit_code':closed['worker_exit_code'],'survivors':closed['survivors'],'original_process_closures':closures}
  result['parent_full_summary_or_DATA']={r:(P/r).exists() for r in ['runtime/output/V8BETA02L_parent_DATA.json','runtime/source/results/V8BETA02L_parent/summary.json']}
  result['prefix_record_equality_established']=nd['prefix_full_record_exact'] is True and rd['prefix_full_record_exact'] is True
  result['parent_full_task_or_motion_PASS']='NOT_ESTABLISHED_PARTIAL_NOT_RANKED'
  result['original_11_hard_value_missing_handling']='UNKNOWN_IF_ABSENT_NEVER_FALSE_BY_DEFAULT'
  result['safety_scope']='ONLY_IDENTICAL_ALREADY_EXECUTED_PARENT_PREFIX_AND_ORIGINAL_B_HARD_COVERAGE;NO_FULL_PARENT_TASK_PASS'
  result['status']='COMPLETED_READ_ONLY_PREFIX_EVIDENCE'
  save(out/'RESULT.json',result)
 except BaseException as error:
  result.update(status='FAILED_OR_INCOMPLETE_NO_RETRY',error_type=type(error).__name__,error=str(error));save(out/'FAILED_PAID_PREFIX.json',result);raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0.)
  save(out/'RESOURCE.json',{'START':initial,'END':usage(),'source_sha256':sha(Path(__file__)),'single_CPU':True,'AS_bytes':1024**3,'external_timeout_s':60,'automatic_retry':False,'new_model_init_forward_fit_physics':0})


if __name__=='__main__':main()
