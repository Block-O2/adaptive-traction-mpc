"""Serial conditional registered sequence. Never tunes using validation outcomes."""
from pathlib import Path
import subprocess,sys,json,time,shutil,hashlib
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
LOCAL=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def run(script,*args):
 subprocess.run([sys.executable,'-B',str(P/'control'/script),*args],cwd=P,check=True)
def eligible(r):return r['motion']['acceptance_pass'] and r['motion']['gain_percent']>=1. and r['task']=='PASS' and r['receipt']=='PASS' and r['absolute_safety']
assert read('reproduction_OWNER.json')['returncode']==0 and read('BASELINE_REPRODUCTION.json')['status']=='PASS'
run('independent_recompute.py','reproduction')
run('own_campaign.py','N2');run('independent_recompute.py','N2')
rows=read('N2_RESULTS.json')['rows'];by={r['arm']:r for r in rows}
selected='C' if eligible(by['C']) else 'R' if 'R' in by and eligible(by['R']) else None
put('DEVELOPMENT_SELECTION.json',dict(selected=selected,unix=time.time(),role='Selection using exposed N2 development only; never validation',C_eligible=eligible(by['C']),R_eligible=eligible(by['R']) if 'R' in by else None,selection_rule='C first if eligible; otherwise single predeclared R if eligible; otherwise stop',candidate_file='CANDIDATE.json' if selected=='C' else 'BOUNDED_REPAIR.json' if selected=='R' else None,validation_started=False))
if selected is None:
 put('SEQUENCE_DECISION.json',dict(status='STOP_PHYSICAL_SEARCH',unix=time.time(),reason='C and one bounded repair did not meet exposed development gate',validation_pairs=0));print('STOP_NO_ELIGIBLE_CANDIDATE');sys.exit(0)
run('own_campaign.py','development');run('independent_recompute.py','development')
dev=next(r for r in read('development_RESULTS.json')['rows'] if r['arm']==selected)
if not eligible(dev):
 put('SEQUENCE_DECISION.json',dict(status='STOP_PHYSICAL_SEARCH',unix=time.time(),reason='Frozen selected candidate failed complete original development compatibility',validation_pairs=0));print('STOP_DEVELOPMENT_FAILED');sys.exit(0)
put('VALIDATION_FREEZE.json',dict(unix=time.time(),selected=selected,candidate_sha256=hashlib.sha256((P/('CANDIDATE.json' if selected=='C' else 'BOUNDED_REPAIR.json')).read_bytes()).hexdigest(),conditions=[r for r in read('RUN_PLAN.json')['validation_conditions'] if r['name'].startswith('U')],no_reselection=True,selection=read('DEVELOPMENT_SELECTION.json')))
for group in ['U1','U2','U3']:
 run('own_campaign.py',group);run('independent_recompute.py',group)
put('SEQUENCE_DECISION.json',dict(status='REGISTERED_SEQUENCE_COMPLETE',unix=time.time(),selected=selected,validation_pairs=3,automatic_next_study=False))
print('SEQUENCE_COMPLETE',selected)
