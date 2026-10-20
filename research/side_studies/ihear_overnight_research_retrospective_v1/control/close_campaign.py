"""Record completed STOP after every authorized physical phase has joined."""
from pathlib import Path
import json,time,datetime,os
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
def load(p):return json.loads(p.read_text())
events=[json.loads(x) for x in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END']
assert len(starts)==len(ends) and {r['id'] for r in starts}=={r['id'] for r in ends}
for name in ['development_repair2','repeat','V1','V2','V3','V4']:
    assert load(S/(name+'_DONE.json'))['all_children_joined']
    assert load(S/'control'/('LAUNCH_'+name+'.json'))['outer_joined']
assert load(S/'VALIDATION_RESULTS.json')['status']=='COMPLETE'
from verify_package import owned_processes
assert not owned_processes(),'OWNED_PHYSICS_REMAINS'
now=time.time();p=load(S/'RUN_PLAN.json');assert now<p['hard_stop_unix']
state=dict(phase='STOP',reason='registered physical campaign and Chinese retrospective complete',unix=now,beijing=datetime.datetime.fromtimestamp(now,datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
           owned_workers=[],all_owned_physics_exited=True,physical_attempt_START=len(starts),physical_attempt_END=len(ends),last_physical_END_unix=max(r['unix'] for r in ends),
           no_new_package_started=True,no_training=True,no_online_adaptation=True,no_final_PPT_or_PDF=True,no_professor_submission=True,
           historical_PHYSICS_STOP_file_retained=True,scientific_success_is_separate_from_package_completion=True)
(S/'STATE.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
(S/'FINAL_STOP.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n');print(json.dumps(state,ensure_ascii=False))
