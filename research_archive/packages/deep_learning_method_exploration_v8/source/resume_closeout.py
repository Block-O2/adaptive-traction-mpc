from pathlib import Path
import os,sys,json,subprocess,runpy,time
P=Path(__file__).resolve().parents[1];A=json.loads((P/'ACTIVATION.json').read_text());assert json.loads((P/'audit/PRESEAL_AUDIT.json').read_text())['status']=='PASS';env=dict(os.environ,ACL2_PACKAGE=str(P),PYTHONPATH=str(P/'source')+':'+str(P/'legacy_source'),PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');steps=[]
(P/'owned/CLOSEOUT_RECOVERY_START.json').write_text(json.dumps(dict(pid=os.getpid(),start_ticks=Path('/proc/self/stat').read_text().split()[21],activation=A['id'],hard_stop_unix=A['hard_stop_unix'],mode='NO_NEW_PHYSICS_REMAINING_REPORT_AND_SEAL_ONLY'),indent=2)+'\n')
for name in ['make_figures.py','write_result_reports.py','append_partial_csv.py','append_partial_notes.py','write_main_report.py']:
 assert time.time()<A['hard_stop_unix'];t=time.time()
 with (P/'logs'/('CLOSEOUT_RECOVERY_'+name+'.log')).open('w') as out:r=subprocess.run([sys.executable,str(P/'source'/name)],env=env,stdout=out,stderr=subprocess.STDOUT,timeout=120)
 steps.append(dict(script=name,returncode=r.returncode,wall_s=time.time()-t));print('RECOVERY_STEP',name,r.returncode,flush=True);assert r.returncode==0,name
(P/'audit/CLOSEOUT_RECOVERY_RECEIPT.json').write_text(json.dumps(dict(status='PASS',original_failure_preserved='audit/CLOSEOUT_FAILURE.json',path_correction='audit/METADATA_PATH_CORRECTION.json',preseal_protection='PASS',steps=steps,activation=A['id'],new_physics=0),indent=2)+'\n')
(P/'owned/CLOSEOUT_RECOVERY_READY_TO_SEAL.json').write_text(json.dumps(dict(pid=os.getpid(),state='FINAL_SEAL',unix=time.time()),indent=2)+'\n')
runpy.run_path(str(P/'source/seal_v4.py'),run_name='__main__')
print('RECOVERY_FINAL_STOP',flush=True)
