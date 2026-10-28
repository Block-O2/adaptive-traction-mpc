"""Independent decoding path, read-only raw, finite wall and attempt bounds."""
import os,sys,time,traceback,signal,json,shutil
from pathlib import Path
from acl2_shared import P,R,put,read,sha,utc,records,native_used
import legacy_independent_audit as ia
A=read('ACTIVATION.json');STOP=A['hard_stop_unix']-600
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('AUDIT_ABSOLUTE_DEADLINE')));signal.alarm(max(1,int(STOP-time.time())))
put('owned/AUDIT_SERVICE_START.json',dict(pid=os.getpid(),utc=utc(),deadline_unix=STOP,source_sha256=sha(Path(__file__)),independent_code_sha256=sha(P/'source/legacy_independent_audit.py')))
for tick in range(20000):
 if time.time()>STOP or (P/'END.json').exists():break
 starts=[r for r in records() if r['event']=='START'];count=0
 for r in starts:
  ident=r['id'];dest=P/'audit/independent'/(ident+'.json')
  if dest.exists():continue
  measured=R/'reports'/(ident+'_MEASURED.json');partial=R/'output'/(ident+'_PARTIAL_COMPUTE.json')
  data=R/'output'/(ident+'_DATA.json')
  if not measured.exists() and not partial.exists():
   if not data.exists() or json.loads(data.read_text()).get('metric',{}).get('task_valid',True):continue
  if not any(s['event']=='END' and s['id']==ident for s in records()):continue
  try:row=ia.audit(ident)
  except BaseException as e:row=dict(id=ident,status='INDEPENDENT_AUDIT_ERROR',error=str(e),traceback=traceback.format_exc())
  row['audit_utc']=utc();put('audit/independent/'+ident+'.json',row);count+=1
 rows=[json.loads(f.read_text()) for f in sorted((P/'audit/independent').glob('*.json'))] if (P/'audit/independent').exists() else []
 mem=dict(s.split(':',1) for s in Path('/proc/meminfo').read_text().splitlines())
 put('audit/INDEPENDENT_RAW_AUDIT.json',dict(status='PASS_SO_FAR' if all(r['status'] in ['PASS','FAILED_TASK_RAW_AUDIT_PASS','PARTIAL_NATIVE_OWNERSHIP_PASS'] for r in rows) else 'REVIEW_REQUIRED',attempt_denominator=len(starts),audited=len(rows),rows=rows,utc=utc(),method='second code path: complete JSON decoding, force/moment quadrature, native-receipt exact torque/count join, native motion derivatives; same agent, not independent investigator'))
 put('RESOURCE_AND_ATTEMPT_ACCOUNTING.json',dict(utc=utc(),T0_utc=A['T0_utc'],elapsed_h=(time.time()-A['t0_unix'])/3600,hard_stop_utc=A['hard_stop_utc'],actual_physical_START=len(starts),actual_new_native_steps_closed=native_used(),completed_END=sum(r['event']=='END' for r in records()),by_category={cat:sum(r.get('category')==cat for r in starts) for cat in ['engineering','optimization','PPO','validation']},available_ram_gib=int(mem['MemAvailable'].split()[0])/2**20,free_disk_gib=shutil.disk_usage(P).free/2**30,independently_audited=len(rows),native_steps_are_not_RL_samples=True,source_sha256=sha(Path(__file__))))
 if count:print('AUDITED',count,'TOTAL',len(rows),'START',len(starts),flush=True)
 time.sleep(6)
put('owned/AUDIT_SERVICE_END.json',dict(pid=os.getpid(),utc=utc(),status='STOP'))
