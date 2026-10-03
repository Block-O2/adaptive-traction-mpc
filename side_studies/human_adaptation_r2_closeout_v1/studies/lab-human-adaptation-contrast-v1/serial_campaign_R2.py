"""Serial frozen primary launcher; one physics process, read-only SAC monitoring."""
from pathlib import Path
import os,sys,json,time,subprocess,csv,resource,hashlib
from datetime import datetime,timezone
W=Path('<SIDE_STUDIES_ROOT>/lab-human-adaptation-contrast-v1')
sys.path.insert(0,str(W));sys.dont_write_bytecode=True
from lab_resource_guard_R2 import sample,gate_reasons
PY='<PYTHON_ENVIRONMENT>/bin/python'
for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1';os.nice(19)
def save(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def utc():return datetime.now(timezone.utc).isoformat()
def update_matrix():
 c=json.loads((W/'CONTRACT_R2.json').read_text());rows=[]
 for e in c['conditions']:
  for arm in c['arms'].values():
   p=W/'runs_R2'/f"{e['id']}__{arm}"/'PRIMARY_RESULT.json'
   rows.append(json.loads(p.read_text()) if p.exists() else dict(condition=e['id'],arm=arm,status='NOT_RUN',physical_verdict='NOT_EVALUATED',scientific_verdict='NOT_EVALUATED'))
 save(W/'PRIMARY_MATRIX_R2.json',dict(status='PRIMARY_IN_PROGRESS',runs=rows))
 fields=['condition','arm','status','physical_verdict','scientific_verdict','mode_overall','outbound_reached','hold_satisfied','true_return_satisfied','duration_s','J_F_task_n_s','force_mean_n','force_rms_n','force_peak_n','moment_integral_nm_s','moment_peak_nm','minimum_clearance_m','minimum_true_clearance_m_evaluation_only','tracking_rmse_rad','abort_reason']
 with (W/'PRIMARY_MATRIX_R2.csv').open('w',newline='') as f:
  out=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');out.writeheader();out.writerows({k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows)
 s=json.loads((W/'STATE_R2.json').read_text());s['primary_runs_completed']=sum(r['status']!='NOT_RUN' for r in rows);s['remaining_primary_budget']=21-s['primary_attempts'];save(W/'STATE_R2.json',s)
 return rows
def pressure(r,base,swap_streak):
 return r['Windows_available_GiB']<1 or r['WSL_available_GiB']<1 or swap_streak>=2 or r['oom_kill_count']>base['oom_kill_count']
def observe(p,initial,samples,peaks):
 previous=initial['swap_used_KiB'];streak=0
 while p.poll() is None:
  try:p.wait(timeout=30)
  except subprocess.TimeoutExpired:pass
  r=sample();samples.append(r)
  streak=streak+1 if r['swap_used_KiB']-previous>65536 else 0;previous=r['swap_used_KiB']
  for x in r['side_workers']:
   try:
    status={k:v for line in (Path('/proc')/str(x['pid'])/'status').read_text().splitlines() if ':' in line for k,v in [line.split(':',1)]}
    peaks[str(x['pid'])]=max(peaks.get(str(x['pid']),0),int(status.get('VmHWM','0 kB').split()[0]))
   except FileNotFoundError:pass
  if r['SAC_heavy_observed']:
   s=json.loads((W/'STATE_R2.json').read_text());s.update(pause_before_next=True,pause_reason='SAC_HEAVY_START_FINISH_CURRENT_RUN');save(W/'STATE_R2.json',s)
  if pressure(r,initial,streak):
   (W/'SIDE_STOP_R2').write_text('Observed memory pressure; own cooperative callback only '+utc()+'\n')
   s=json.loads((W/'STATE_R2.json').read_text());s.update(pause_before_next=True,pause_reason='SIDE_MEMORY_PRESSURE');save(W/'STATE_R2.json',s)
 return p.returncode
def run(condition,arm):
 dest=W/'runs_R2'/f'{condition}__{arm}'
 if (dest/'PRIMARY_RESULT.json').exists():return
 assert not dest.exists(),'An unfinished primary slot must be classified/repaired before launch; never silently rerun.'
 s=json.loads((W/'STATE_R2.json').read_text())
 if s.get('pause_before_next'):raise RuntimeError('READY_WAITING_FOR_RESOURCES:'+str(s.get('pause_reason')))
 r=sample();peer=json.loads((W/'SAC_PHASE_OBSERVATION_R2.json').read_text());qual=json.loads((W/'RESOURCE_DYNAMIC_QUALIFICATION.json').read_text())
 reasons=gate_reasons(r,peer,qual)
 if reasons:raise RuntimeError('READY_WAITING_FOR_RESOURCES:'+','.join(reasons))
 env=dict(os.environ,LAB_STUDY_ARM=arm);start=utc();wall=time.monotonic();samples=[r];peaks={}
 log=W/'run_logs_R2';log.mkdir(exist_ok=True)
 with (log/f'{condition}__{arm}.txt').open('w') as stream:
  p=subprocess.Popen([PY,'-B','-u',str(W/'human_qualification_R2.py'),'--execute',condition],env=env,stdout=stream,stderr=subprocess.STDOUT)
  print('LAUNCH',condition,arm,p.pid,flush=True)
  code=observe(p,r,samples,peaks)
 qpath=dest/'qualification.json';q=json.loads(qpath.read_text()) if qpath.exists() else None
 record=dict(condition=condition,arm=arm,start_utc=start,end_utc=utc(),process_exit=code,wall_s=time.monotonic()-wall,samples=samples,per_PID_sampled_VmHWM_KiB=peaks,parent_ru_maxrss_KiB=None if q is None else q.get('peak_RSS_KiB'),children_ru_maxrss_KiB=None if q is None else q.get('children_peak_RSS_KiB'),sampled_aggregate_RSS_peak_KiB=max(x['side_parent_children_RSS_KiB'] for x in samples),Windows_available_min_GiB=min(x['Windows_available_GiB'] for x in samples),WSL_available_min_GiB=min(x['WSL_available_GiB'] for x in samples),swap_peak_KiB=max(x['swap_used_KiB'] for x in samples),memory_pressure_observed=any(pressure(x,r,0) for x in samples),SAC_heavy_during_run=any(x['SAC_heavy_observed'] for x in samples),SAC_workers_during_run=[x['SAC_python_workers'] for x in samples if x['SAC_python_workers']],clean_wall_benchmark=False)
 dest.mkdir(exist_ok=True);save(dest/'RESOURCE_RUN.json',record)
 if q is None:raise RuntimeError('HARNESS_EXIT_WITHOUT_QUALIFICATION: inspect '+str(dest))
 # No physics process remains while scorer runs.
 analysis_start=time.monotonic()
 with (log/f'{condition}__{arm}__scorer.txt').open('w') as stream:
  pc=subprocess.Popen([PY,'-B',str(W/'postprocess_lab_run_R2.py'),str(dest)],stdout=stream,stderr=subprocess.STDOUT)
  code=observe(pc,r,[],{})
 s=json.loads((W/'STATE_R2.json').read_text());s['active_seconds']+=time.monotonic()-analysis_start;save(W/'STATE_R2.json',s)
 if code:raise RuntimeError('POSTPROCESS_FAILURE:'+str(dest))
 rows=update_matrix();result=json.loads((dest/'PRIMARY_RESULT.json').read_text())
 print('RESULT',condition,arm,result['status'],result['physical_verdict'],result['scientific_verdict'],result.get('J_F_task_n_s'),len([x for x in rows if x['status']!='NOT_RUN']),flush=True)
 try:
  # Verified compact evidence first; compress own redundant runtime JSON, never delete prior evidence.
  import gzip
  for name in ['model_consumption_','prediction_updates_','TASK_PREDICTION_SAMPLES']:
   for path in dest.glob(name+'*.jsonl'):
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    with gzip.open(str(path)+'.gz','wb',compresslevel=3) as f:
     with path.open('rb') as src:
      import shutil;shutil.copyfileobj(src,f)
    with gzip.open(str(path)+'.gz','rb') as f:assert hashlib.sha256(f.read()).hexdigest()==digest
    path.unlink()
 except Exception as e:print('RETENTION_COMPRESSION_WARNING',type(e).__name__,str(e),flush=True)
if __name__=='__main__':
 fd=os.open(W/'SERIAL_LAUNCHER_R2.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  c=json.loads((W/'CONTRACT_R2.json').read_text())
  for condition in sys.argv[1:]:
   assert condition in [x['id'] for x in c['conditions']]
   for arm in c['arms'].values():run(condition,arm)
 except Exception as e:
  s=json.loads((W/'STATE_R2.json').read_text());s.update(status='READY_WAITING_FOR_RESOURCES' if 'READY_WAITING' in str(e) else 'PARTIAL',last_launcher_issue=str(e));save(W/'STATE_R2.json',s)
  print(type(e).__name__,str(e),flush=True);sys.exit(2)
 finally:(W/'SERIAL_LAUNCHER_R2.lock').unlink(missing_ok=True)
