"""Conditional fixed phase-policy confirmation after the finite research queue."""
from pathlib import Path
import os,sys,time,json,hashlib,subprocess,ast,itertools
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
import numpy as np
P=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(P/'source'),str(P/'runtime/code'),str(P/'runtime/deps')]
from stream_runtime_evidence import array_items
from v6_data import group as collect
def read(n):return json.loads((P/n).read_text())
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def put(n,x):
 q=P/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
start=time.time();deadline=read('ACTIVATION.json')['hard_stop_unix'];status='WAITING';reason=None;rows=[]
put('owned/PHASE_RULE_FOLLOWUP_START.json',dict(pid=os.getpid(),started_unix=start,source_sha256=sha(Path(__file__)),deadline_unix=deadline))
try:
 while not (P/'owned/ADAPTIVE_RULE_DRIVER_V3_END.json').exists():
  assert time.time()<deadline-2400,'NO_CLOSEOUT_RESERVE'
  time.sleep(5)
 prior=read('owned/ADAPTIVE_RULE_DRIVER_V3_END.json');assert prior['status']!='REVIEW_REQUIRED','ADAPTIVE_BRANCH_REQUIRES_REVIEW'
 outcome=read('analysis/ADAPTIVE_FIXED_RULE_RESULTS.json');protocol=read('freeze/FIXED_PHASE_RULE_FOLLOWUP.json')
 if outcome['status']=='COMPLETED_FROZEN_CONFIRMATIONS':status='NOT_RUN';reason='Targeted RULE confirmed; no additional fixed-phase trials within cap.'
 else:
  reference={}
  for g in ['SMOOTH_A1','SMOOTH_A2']:
   reference[g]={r['tag']:r for r in read('data/'+g+'.json') if r['horizon_s']==.5}
  if not all(reference[g]['COMPOSE']['qualified'] for g in reference):
   status='NOT_RUN';reason='Matched COMPOSE reference not original-qualified; do not weaken reference.'
  else:
   starts=sum(json.loads(s)['event']=='START' for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines())
   if starts+6>read('runtime/RUN_PLAN.json')['physics_budget'] or deadline-time.time()<4200:
    status='NOT_RUN';reason='Insufficient six-attempt budget or40min closeout reserve plus measured trial margin.'
   else:
    assert sha(P/'source/v6_common_worker.py')==protocol['worker_sha256']
    src=P/'runtime/control/base_campaign.py';tree=ast.parse(src.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw');scope=dict(np=np,itertools=itertools,array_items=array_items);exec(compile(ast.Module(body=[fn],type_ignores=[]),str(src),'exec'),scope)
    for g in ['PHASE_RULE_S1','PHASE_RULE_S2']:
     cfg=P/'experiments'/f'{g}.json';assert sha(cfg)==protocol['configs_sha256'][g]
     with (P/'logs'/f'{g}_followup_supervisor.log').open('w') as log:
      rc=subprocess.run([sys.executable,'-B',str(P/'source/supervise_v2.py'),f'experiments/{g}.json'],env=dict(os.environ,ACL2_PACKAGE=str(P)),stdout=log,stderr=subprocess.STDOUT,timeout=max(1,deadline-time.time()-2400)).returncode
     assert rc==0,'FIXED_PHASE_JOB_FAILED:'+g
     actual={r['tag']:r for r in collect(g,wrench=True) if r['horizon_s']==.5};ref=read('experiments/'+g+'.json')['matched_reference_group']
     identity=scope['compare_raw'](P/'runtime/source/results'/(g+'_B'),P/'runtime/source/results'/(ref+'_B'));put('audit/'+g+'_MATCHED_REFERENCE_B_RAW_IDENTITY.json',identity);assert identity['status']=='PASS','FIXED_PHASE_REFERENCE_IDENTITY_MISMATCH'
     a=actual['HANDOFF'];c=reference[ref]['COMPOSE'];av=np.r_[a['metrics']['full_jerk_RMS_deg_s3'],a['metrics']['wrench']['force_norm_rate_RMS_N_s']];cv=np.r_[c['metrics']['full_jerk_RMS_deg_s3'],c['metrics']['wrench']['force_norm_rate_RMS_N_s']];rat=av/cv;djf=a['metrics']['full_JF']-c['metrics']['full_JF'];djm=a['metrics']['full_JM']-c['metrics']['full_JM'];passed=bool(a['qualified'] and c['qualified'] and np.all(rat<=[1.001,1.001,1.004]) and djf<0 and djm<=0)
     rows.append(dict(group=g,reference_group=ref,original_qualified=a['qualified'],COMPOSE_original_qualified=c['qualified'],
      phase_rule_JF=a['metrics']['full_JF'],phase_rule_JM=a['metrics']['full_JM'],delta_JF_vs_COMPOSE=djf,delta_JM_vs_COMPOSE=djm,
      hip_knee_jerk_force_rate_ratio_vs_COMPOSE=rat.tolist(),predeclared_extra_quality_and_cost_bounds_pass=passed,
      all_metrics=a['metrics'],reference_metrics=c['metrics'],classification='adaptive paired fixed-policy confirmation; baseline state partially exposed, no new unseen-model claim'))
     put('analysis/FIXED_PHASE_RULE_RESULTS.json',dict(status='IN_PROGRESS',rows=rows,reason=None))
    status='COMPLETED_TWO_PAIRED_CONFIRMATIONS'
 put('analysis/FIXED_PHASE_RULE_RESULTS.json',dict(status=status,reason=reason,rows=rows,started_unix=start,ended_unix=time.time(),
  selection='fixed OUT1 HANDOFF then commonCOMPOSE; no model, no new parameter optimization',
  reference_reuse='actual complete matchedCOMPOSE and new exact fullB identity; invalidBEST never ranked as successful'))
finally:
 put('owned/PHASE_RULE_FOLLOWUP_END.json',dict(pid=os.getpid(),ended_unix=time.time(),status=status,reason=reason))
 print('PHASE_RULE_FOLLOWUP',status,reason,flush=True)
