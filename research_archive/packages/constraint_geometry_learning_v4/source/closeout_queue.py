"""Finite executable closeout, independent of future Codex reasoning or client SSH."""
from pathlib import Path
import os,sys,json,time,subprocess,runpy,traceback
P=Path(__file__).resolve().parents[1];A=json.loads((P/'ACTIVATION.json').read_text());deadline=A['hard_stop_unix'];start=P/'owned/CLOSEOUT_QUEUE_START.json';assert not start.exists(),'UNIQUE_CLOSEOUT_QUEUE';start.write_text(json.dumps(dict(pid=os.getpid(),start_ticks=Path('/proc/self/stat').read_text().split()[21],activation=A['id'],deadline_unix=deadline,finite=True),indent=2)+'\n');env=dict(os.environ,ACL2_PACKAGE=str(P),PYTHONPATH=str(P/'source')+':'+str(P/'legacy_source'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');steps=[]
def run(name,script,cap=600):
 assert time.time()<deadline,'ACTIVATION_DEADLINE';begin=time.time();log=P/'logs'/('CLOSEOUT_'+name+'.log')
 with log.open('w') as out:r=subprocess.run([sys.executable,str(P/script)],env=env,stdout=out,stderr=subprocess.STDOUT,timeout=max(1,min(cap,deadline-time.time())))
 row=dict(name=name,script=script,returncode=r.returncode,wall_s=time.time()-begin);steps.append(row);(P/'audit/CLOSEOUT_STEP_ACCOUNTING.json').write_text(json.dumps(steps,indent=2)+'\n');print('CLOSEOUT_STEP',name,r.returncode,flush=True);assert r.returncode==0,'CLOSEOUT_STEP_FAILED:'+name
try:
 while not (P/'owned/FACTOR_VALIDATION_QUEUE_END.json').exists():
  assert time.time()<deadline-600,'CLOSEOUT_RESERVE_EXHAUSTED'
  time.sleep(2)
 final=json.loads((P/'owned/FACTOR_VALIDATION_QUEUE_END.json').read_text());assert final['reason']=='FINITE_VAL_C_COMPLETED','FROZEN_PHYSICAL_QUEUE_FAILED'
 (P/'CLOSURE_START.json').write_text(json.dumps(dict(unix=time.time(),activation=A['id'],no_new_physics=True))+'\n')
 for _ in range(30):
  if (P/'owned/SCORER_SERVICE_END.json').exists():break
  time.sleep(1)
 assert (P/'owned/SCORER_SERVICE_END.json').exists(),'SCORER_SERVICE_DID_NOT_STOP'
 for name,script,cap in [('branches','source/analyze_completed.py',600),('safety_partials','source/augment_safety_and_partials.py',120),('scorer_final','source/recompute_completed.py',600),('accounting','source/aggregate_results.py',120),('requests','source/compare_request_pairs.py',120),('historical_and_factor_identity','source/reference_identity_audit.py',600),('receipt_native_identity','source/receipt_audit_v4.py',600),('fresh_timings','source/timing_probe.py',120),('protected_manifests','source/verify_protected_inputs.py',300),('protection_audit','source/preseal_audit.py',180),('figures','source/make_figures.py',120),('result_reports','source/write_result_reports.py',120),('csv_partials','source/append_partial_csv.py',120),('partial_notes','source/append_partial_notes.py',120),('main_report','source/write_main_report.py',120)]:run(name,script,cap)
 (P/'owned/CLOSEOUT_QUEUE_READY_TO_SEAL.json').write_text(json.dumps(dict(pid=os.getpid(),state='FINAL_SEAL',activation=A['id'],steps=len(steps),unix=time.time()),indent=2)+'\n')
 # Final seal executes in this process and produces the last package writes.
 runpy.run_path(str(P/'source/seal_v4.py'),run_name='__main__');print('FINITE_CLOSEOUT_STOP',flush=True)
except BaseException as error:
 d=dict(state='STOP',verification_pass=False,error=repr(error),traceback=traceback.format_exc(),activation=A['id'],ended_unix=time.time(),steps=steps);(P/'audit/CLOSEOUT_FAILURE.json').write_text(json.dumps(d,indent=2)+'\n');(P/'STATUS.json').write_text(json.dumps(dict(state='STOP',verification='CLOSEOUT_NEEDS_REVIEW',error=repr(error)),indent=2)+'\n');print('CLOSEOUT_ERROR',repr(error),flush=True);raise
