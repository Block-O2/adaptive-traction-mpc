from pathlib import Path
import json,hashlib,time
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
assert not any(json.loads(s)['id'].startswith('U') for s in (P/'ATTEMPTS.jsonl').read_text().splitlines())
names=['feedback_selector.py','prepare_repetition.py','repetition_runner.py','repetition_owner.py','repetition_pipeline.py']
record=dict(unix=time.time(),scope='Design identity before primary U outcomes; subsequent protocol uses exposed W2 continuous-session pilot, not a new blind test.',files={n:hashlib.sha256((R/'control'/n).read_bytes()).hexdigest() for n in names},condition='D02 exposed W2 prefix and seed',value_head_training='D training parents only; alpha selected on V parents; never U outcomes',sequential_feedback='actual first completed measured-force integral, one clipped kernel value update; next actual task with original persistent API',success='feedback changes chosen action and actual qualified benefit versus matched next-task H150; no forced changes')
(P/'audit/REPETITION_DESIGN_BEFORE_TEST.json').write_text(json.dumps(record,indent=2)+'\n')
print('REPETITION_DESIGN_IDENTITY_REGISTERED',flush=True)
