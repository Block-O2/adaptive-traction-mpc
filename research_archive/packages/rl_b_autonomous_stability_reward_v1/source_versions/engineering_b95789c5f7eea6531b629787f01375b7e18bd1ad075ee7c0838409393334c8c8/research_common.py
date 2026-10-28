"""Durable campaign bookkeeping. No physics/controller dependency."""
from pathlib import Path
from datetime import datetime, timezone
import contextlib, fcntl, hashlib, json, os, shutil, time

ROOT = Path(os.environ.get('IHEAR_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))
RUNTIME = ROOT / 'runtime'
STATE = json.loads((ROOT / 'START.json').read_text())
HARD_STOP = datetime.fromisoformat(STATE['hard_stop_utc']).timestamp()
NO_TRAIN = datetime.fromisoformat(STATE['no_new_training_utc']).timestamp()
RESERVATION = 165000

def now(): return datetime.now(timezone.utc).isoformat()
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(4 * 1024**2), b''): h.update(b)
    return h.hexdigest()
def atomic(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + f'.writing.{os.getpid()}')
    with temp.open('w') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temp, p)
def append(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('a') as f:
        f.write(json.dumps(obj, ensure_ascii=False, allow_nan=False) + '\n')
        f.flush(); os.fsync(f.fileno())
def decision(event, evidence, next_action, **kw):
    current=read(ROOT/'LEDGER.json',{})
    budget=dict(training_attempts=current.get('training_attempts',0),
         evaluation_attempts=current.get('evaluation_attempts',0),native_steps=current.get('native_steps',0),
         training_hard_cap=450,evaluation_hard_cap=60,native_hard_cap=50000000,
         remaining_wall_s=max(0.,HARD_STOP-time.time()),no_new_training_unix=NO_TRAIN,hard_stop_unix=HARD_STOP)
    defaults=dict(budget=budget,hypotheses_accepted=[],hypotheses_rejected=[],
         risks=['Known nominal only; incomplete G4/live matched/independent initial-state qualification'],
         stop_conditions=['10-hour hard deadline','450 training/60 evaluation/50M native caps',
                          'New actual safety or future-truth leak','Evidence corruption or persistent resource-control failure'])
    append(ROOT / 'RESEARCH_DECISION_LOG.jsonl', dict(time_utc=now(), event=event,
           evidence=evidence, next=next_action, **{**defaults,**kw}))
def read(p, default=None): return json.loads(Path(p).read_text()) if Path(p).exists() else default
def resources():
    mem = {k:int(v.split()[0])*1024 for k,v in
           (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())}
    return dict(unix=time.time(), available_bytes=mem['MemAvailable'],
                disk_free_bytes=shutil.disk_usage(ROOT).free)
def check_resources():
    row = resources()
    if row['available_bytes'] < 6 * 1024**3: raise RuntimeError('GLOBAL_RAM_RESERVE')
    if row['disk_free_bytes'] < 10 * 1024**3: raise RuntimeError('GLOBAL_DISK_RESERVE')
    if time.time() >= HARD_STOP: raise RuntimeError('HARD_STOP')
    if (ROOT / 'STOP_REQUESTED').exists(): raise RuntimeError('EXPLICIT_STOP_REQUESTED')
    return row
@contextlib.contextmanager
def ledger():
    with (ROOT / '.ledger.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        value = read(ROOT/'LEDGER.json', dict(attempts=[], native_steps=0,
                   training_attempts=0, evaluation_attempts=0, optimizer_steps=0,
                   rl_decisions=0, gradient_train_calls=0))
        yield value
        atomic(ROOT/'LEDGER.json', value)
def reserve(kind, job, run, index):
    check_resources()
    if kind=='training' and time.time() >= NO_TRAIN: raise RuntimeError('NO_NEW_TRAINING_WINDOW')
    # Leave five minutes for evaluation cleanup at the final hard deadline.
    if time.time() >= HARD_STOP-300: raise RuntimeError('NO_NEW_PHYSICS_CLEANUP')
    with ledger() as value:
        key=kind+'_attempts'; cap=450 if kind=='training' else 60
        if value[key] >= cap: raise RuntimeError('ATTEMPT_HARD_CAP')
        outstanding=sum(a['reserved_native_steps'] for a in value['attempts'] if not a['settled'])
        if outstanding: raise RuntimeError('CONCURRENT_PHYSICS_DENIED_SINGLE_ENVIRONMENT')
        if value['native_steps']+outstanding+RESERVATION > 50000000:
            raise RuntimeError('NATIVE_RESERVATION_HARD_CAP')
        identity=f'{job}:{index}:{kind}'
        if any(a['id']==identity for a in value['attempts']): raise RuntimeError('ATTEMPT_ID_REUSED')
        a=dict(id=identity, kind=kind, job=job, run=str(run), index=index,
               start_utc=now(), settled=False, reserved_native_steps=RESERVATION,
               pid=os.getpid())
        value['attempts'].append(a); value[key]+=1
        native_before=value['native_steps']+outstanding
    return identity, native_before
def settle(identity, native, decisions, optimizer=0, outcome=None):
    assert 0 <= native <= RESERVATION
    with ledger() as value:
        a=next(a for a in value['attempts'] if a['id']==identity)
        if a['settled']: raise RuntimeError('ATTEMPT_DOUBLE_SETTLE')
        a.update(settled=True, native_steps=int(native), rl_decisions=int(decisions),
                 optimizer_steps=int(optimizer), outcome=outcome, end_utc=now())
        value['native_steps']+=int(native); value['rl_decisions']+=int(decisions)
        value['optimizer_steps']+=int(optimizer)
        value['gradient_train_calls']+=int(optimizer>0)
def pid_identity(pid):
    try:
        s=Path(f'/proc/{pid}/stat').read_text(); fields=s[s.rfind(')')+2:].split()
        return dict(pid=pid,start_ticks=fields[19],state=fields[0])
    except FileNotFoundError: return None
def same_pid(identity):
    x=pid_identity(identity['pid']) if identity else None
    return bool(x and x['start_ticks']==identity['start_ticks'] and x['state']!='Z')
