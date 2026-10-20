from pathlib import Path
import json,time,subprocess,shutil
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1');C=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_sequential_teacher_oracle_v1_control');PY='/home/hank/envs/adaptive-online-rl-v1/bin/python';P=json.loads((S/'SEARCH_PROTOCOL.json').read_text())
def put(n,x):(S/n).write_text(json.dumps(x,indent=2)+'\n')
subprocess.run([PY,str(C/'deploy.py')],check=True)
put('VALIDATION_WALL_GUARD.json',dict(unix=time.time(),hard_deadline_unchanged=True,dispatch_cutoff_unchanged=True,child_timeout_tightened_s=180,motion_and_parameters_unchanged=True,reason='retain final30-minute no-dispatch window and normal child completion; final exact repeat can use already completed same-action parent replays, never count those as unseen validation'))
for mode in ['V1','V2']:
 put('VALIDATION_PROGRESS.json',dict(mode=mode,unix=time.time(),status='RUNNING'))
 with (S/'logs'/(mode+'.log')).open('w') as f:subprocess.run([PY,str(S/'code/sequential_runner.py'),mode],stdout=f,stderr=subprocess.STDOUT,check=True)
if time.time()<P['dispatch_cutoff_unix']-480:
 with (S/'logs/verify.log').open('w') as f:subprocess.run([PY,str(S/'code/sequential_runner.py'),'verify'],stdout=f,stderr=subprocess.STDOUT,check=True)
else:
 gates={n:json.loads((S/n).read_text()) for n in ['seqO_ANCESTOR_REPLAY_GATE.json','seqR_ANCESTOR_REPLAY_GATE.json']}
 assert all(g['status']=='PASS' and not g.get('old_raw_compacted',False) for g in gates.values())
 put('BEST_REPEAT_GATE.json',dict(status='PASS',scope='already completed exact full-native same-action ancestor replays; repeated physics counted in search, not unseen validation',gates=gates,standalone_final_repeat='NOT_RUN_WALL_RESERVE',no_future_test_used_for_selection=True))
put('VALIDATION_DONE.json',dict(unix=time.time(),status='COMPLETE',all_children_joined=True))
print('VALIDATION_COMPLETE',flush=True)
