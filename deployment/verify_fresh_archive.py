#!/usr/bin/env python3
"""Finite archive acceptance in an independently cloned repository.

Install the opt-in deployment/tests access guard into a disposable venv first.
No training, search, hardware or cloud-resource APIs. All output directories new.
"""
from __future__ import annotations
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-commit',required=True);p.add_argument('--timeout-s',type=int,default=900);a=p.parse_args()
 if not __debug__:raise SystemExit('Qualification assertions require normal Python')
 repo=a.repo.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
 if not (repo/'.git').is_dir():raise SystemExit('A standalone clone with its own .git directory is required')
 if (repo/'.git/objects/info/alternates').exists():raise SystemExit('Local object alternates are forbidden')
 head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
 if head!=a.expected_commit:raise SystemExit('Remote payload commit mismatch')
 if not os.environ.get('IHEAR_FORBIDDEN_ROOTS') or '_ihear_fresh_clone_guard' not in sys.modules:raise SystemExit('Install and activate the disposable Python access guard first')
 env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLBACKEND='Agg',MPLCONFIGDIR=str(out/'mpl'))
 steps=[];start=time.time()
 def run(name,args,limit=600):
  t=time.time();log=out/(name+'.log')
  with log.open('w') as f:
   proc=subprocess.Popen([sys.executable,'-B',*map(str,args)],cwd=repo,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
   try:rc=proc.wait(timeout=limit);status='PASS' if rc==0 else 'FAIL'
   except subprocess.TimeoutExpired:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    rc=proc.returncode;status='TIMEOUT_OWNED_GROUP_TERMINATED'
  row=dict(name=name,status=status,returncode=rc,wall_s=time.time()-t,log=log.name,command=[sys.executable,'-B',*map(str,args)])
  steps.append(row);(out/'PROGRESS.json').write_text(json.dumps(dict(commit=head,steps=steps),indent=2)+'\n');print(json.dumps({k:row[k] for k in ['name','status','wall_s']}) ,flush=True)
 run('static',['deployment/archive_checks.py','--output',out/'STATIC.json'])
 run('baseline_identity',['deployment/verify_repository.py','--expected-commit',head,'--output',out/'BASELINE_IDENTITY.json'])
 run('models',['deployment/check_models.py','--output',out/'MODELS.json'])
 run('original_d01r_offline',['deployment/score_b_h150.py','--work-dir',out/'d01r_offline'])
 run('original_v7_offline',['deployment/score_archive_combo.py','--repo',repo,'--output',out/'v7_offline'])
 run('learning_interface',['deployment/check_learning_interface.py','--repo',repo,'--output',out/'learning'])
 run('rl_b_contract',['deployment/check_rl_b.py','--work-dir',out/'rl_b_contract'])
 run('rebuild_figures',['figures/rebuild_archive_evidence.py','--source-root',repo/'research_archive/packages','--output-dir',out/'rebuilt_figures'])
 run('original_b_dynamic',['deployment/reproduce_original_b.py','--repo',repo,'--output',out/'original_b','--timeout-s',a.timeout_s],a.timeout_s+180)
 run('strong_traditional_dynamic',['deployment/reproduce_trad_combo.py','--repo',repo,'--output',out/'combo','--timeout-s',a.timeout_s],6*a.timeout_s+1200)
 run('d01r_dynamic',['deployment/reproduce_traditional.py','--repo',repo,'--output',out/'d01r','--timeout-s',a.timeout_s],5*a.timeout_s+1200)
 guardlog=Path(os.environ['IHEAR_ACCESS_GUARD_LOG']);guard_events=guardlog.read_text().splitlines() if guardlog.exists() else []
 result=dict(schema='ihear.archive.fresh_remote_acceptance.v1',status='PASS' if all(x['status']=='PASS' for x in steps) and not guard_events else 'FAIL',source_commit=head,remote=subprocess.check_output(['git','-C',str(repo),'remote','get-url','origin'],text=True).strip(),clone_owns_git_objects=True,local_object_alternates=False,started_unix=start,finished_unix=time.time(),wall_s=time.time()-start,steps=steps,forbidden_roots=json.loads(os.environ['IHEAR_FORBIDDEN_ROOTS']),forbidden_python_file_access_events=len(guard_events),isolation_limit='Python audit hook, not an OS sandbox; archive model/source path rebasing and actual clone provenance also checked.',new_training_steps=0,hardware='NOT_RUN',host_realtime='NOT_EVALUABLE',paid_cloud_resources_created=0)
 (out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],result=str(out/'RESULT.json'),wall_s=result['wall_s'])),flush=True)
 return 0 if result['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
