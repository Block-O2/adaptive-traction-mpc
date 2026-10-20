"""Separate, append-only extension evidence; accepted delivery remains immutable."""
from task_bootstrap import *
EXT = STUDY / 'extension_to_noon'
DEADLINE = 1791345600
FIRST_DELIVERY = Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/delivery')
WIN_EXT = FIRST_DELIVERY.parent / 'extension_to_noon'

def append(name, row):
    EXT.mkdir(exist_ok=True)
    with (EXT/name).open('a') as f:
        f.write(json.dumps(row, allow_nan=False)+'\n')

def guard(reserve=0):
    assert time.time() < DEADLINE-reserve, 'NOON_EXTENSION_DEADLINE'

def register_imports(name):
    rows=[]
    for module in list(sys.modules.values()):
        source=getattr(module,'__file__',None)
        if not source: continue
        p=Path(source)
        if p.suffix=='.py' and p.is_file() and p.is_relative_to(STUDY):
            rows.append(dict(path=str(p),sha256=sha(p)))
    save(EXT/(name+'_IMPORTED_SOURCES.json'), sorted({r['path']:r for r in rows}.values(),key=lambda r:r['path']))
