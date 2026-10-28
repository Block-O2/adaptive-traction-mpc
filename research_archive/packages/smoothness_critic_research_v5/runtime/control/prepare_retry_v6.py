"""Retain v5 launch error and correct its unique log name before any worker."""
from pathlib import Path
import json,time,hashlib,ast,shutil,os
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
assert not (P/'REPETITION_RETRY_OWNER.json').exists()
assert not any(json.loads(s)['id'].startswith('REPR') for s in (P/'ATTEMPTS.jsonl').read_text().splitlines())
assert not (P/'EXECUTION_CODE_MANIFEST_v6.json').exists()
now=time.time();ident='REPR_owner_log_failure'
failure=dict(error='FileExistsError opening existing logs/REPETITION.log with exclusive creation',before_worker_launch=True,new_native_steps=0,owner_source_sha256=sha(P/'control/repetition_owner_v5.py'),prior_log_preserved=True,recorded_unix=now,wall_duration_measured=False)
put('audit/OWNER_LAUNCH_FAILURE_v5.json',failure)
with (P/'ATTEMPTS.jsonl').open('a') as f:
    for event in ['START','END']:
        row=dict(unix=now,event=event,id=ident,pid=os.getpid(),kind='OWNER_LAUNCH_FAILED_BEFORE_WORKER',retrospective_pre_worker_failure=True,event_time_semantics='logging time; exact failed launcher wall duration not measured',code_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST_v5.json'))
        if event=='END':row.update(returncode=1,joined=True,actual_new_native_steps=0,error=failure['error'])
        f.write(json.dumps(row)+'\n')
for src,dst in [('campaign_v5.py','campaign_v6.py'),('repetition_runner_v5.py','repetition_runner_v6.py'),('repetition_owner_v5.py','repetition_owner_v6.py')]:
    s=(P/'control'/src).read_text().replace('_v5','_v6')
    if 'owner' in dst:s=s.replace('logs/REPETITION.log','logs/REPETITION_RETRY_v6.log')
    ast.parse(s);(P/'control'/dst).write_text(s)
shutil.copy2(Path(__file__),P/'control/prepare_retry_v6.py')
files=dict(read('EXECUTION_CODE_MANIFEST_v5.json')['files'])
for n in ['control/campaign_v6.py','control/repetition_runner_v6.py','control/repetition_owner_v6.py','control/prepare_retry_v6.py']:files[n]=sha(P/n)
put('EXECUTION_CODE_MANIFEST_v6.json',dict(files=files,frozen_unix=time.time(),change='Unique retry owner log name; v5 policy/serializer repair unchanged. No v5 worker or physics ran.',previous_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST_v5.json')))
put('PREPHYSICAL_CHECKS_v6.json',dict(status='PASS',AST=True,serializer_probe='audit/SERIALIZER_REPAIR_PREPHYSICAL.json',unique_log_name=True,planned_total_START=83))
put('PHYSICS_STOP_v5.json',dict(unix=time.time(),reason='Retired unexecuted worker version after exclusive log-path failure; v6 has unique log and unchanged policy'))
print('RETRY_V6_PREPARED',flush=True)
