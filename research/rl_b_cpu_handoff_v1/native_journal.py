"""Opt-in lossless native-state journal: identical rows, bounded storage memory."""
from pathlib import Path
import os,json,itertools
from common import clean,ROOT
class NativeJournal:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.writer=self.path.open('x',encoding='utf-8',buffering=65536);self.count=0
    def append(self,row):
        self.writer.write(json.dumps(clean(row),separators=(',',':'),allow_nan=False)+'\n');self.count+=1
        if self.count%256==0:self.writer.flush()
    def __len__(self):return self.count
    def __iter__(self):
        if not self.writer.closed:self.writer.flush()
        with self.path.open(encoding='utf-8') as f:
            for line in f:yield json.loads(line)
    def close(self):
        if not self.writer.closed:self.writer.close()
    def __del__(self):self.close()
def write_artifact(path,payload):
    # Preserve the original JSON schema while avoiding a second full native
    # array and the huge indented JSON string in memory at finalization.
    def emit(f,x):
        if isinstance(x,NativeJournal) and os.environ.get('IHEAR_EXTERNAL_NATIVE')=='1':
            if not x.writer.closed:x.writer.flush()
            emit(f,{'external_jsonl_relative_to_study':x.path.relative_to(ROOT).as_posix(),'count':len(x),'format':'unchanged_native_rows_v1'})
        elif isinstance(x,dict):
            f.write('{')
            for i,(key,value) in enumerate(x.items()):
                if i:f.write(',')
                f.write(json.dumps(str(key))+':');emit(f,value)
            f.write('}')
        elif isinstance(x,(list,tuple,NativeJournal)):
            f.write('[')
            for i,value in enumerate(x):
                if i:f.write(',')
                emit(f,value)
            f.write(']')
        else:f.write(json.dumps(clean(x),separators=(',',':'),allow_nan=False))
    path=Path(path);temporary=path.with_suffix(path.suffix+'.writing')
    if os.environ.get('IHEAR_EXTERNAL_NATIVE')=='1':payload={**payload,'native_evidence_format':'external_jsonl_v1'}
    with temporary.open('w',encoding='utf-8',buffering=65536) as f:emit(f,payload);f.write('\n')
    os.replace(temporary,path)
def install():
    from traction_mpc_stage5.full3d_adaptive_integration_v1.wall_physics import WallPhysicsSession
    if getattr(WallPhysicsSession,'_native_journal_installed',False):return
    init=WallPhysicsSession.__init__;release=WallPhysicsSession.release_runtime_maintenance;sequence=itertools.count(1)
    def initialize(self,*args,**kwargs):
        init(self,*args,**kwargs)
        assert not self.native_states,'JOURNAL_MUST_START_BEFORE_NATIVE_STEPS'
        self.native_states=NativeJournal(Path(os.environ['IHEAR_RUN_DIR'])/'native_journals'/f'native_{next(sequence):04d}.jsonl')
    def cleanup(self):
        try:release(self)
        finally:self.native_states.close()
    WallPhysicsSession.__init__=initialize;WallPhysicsSession.release_runtime_maintenance=cleanup;WallPhysicsSession._native_journal_installed=True
