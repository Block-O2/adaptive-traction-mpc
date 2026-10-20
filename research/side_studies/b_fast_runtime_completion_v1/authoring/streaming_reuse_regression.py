from pathlib import Path
import sys,json,types
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'));sys.path.insert(0,'/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_fast_runtime_completion_v1')
import streaming_reuse as r
class FakeRT:pass
rt=FakeRT();rt.persist_runtime_artifacts=lambda *args:'original';calls=[]
def install(rt):calls.append(rt);rt.persist_runtime_artifacts=lambda *args:'streaming'
memory=types.SimpleNamespace(install=install)
base=r.ensure(rt,memory);assert r.ensure(rt,memory) is base and len(calls)==1
rt.persist_runtime_artifacts=lambda *args:'previous run closure';r.restore(rt)
assert rt.persist_runtime_artifacts is base and r.ensure(rt,memory) is base
rt.persist_runtime_artifacts=lambda *args:'unexpected owner'
try:r.ensure(rt,memory)
except AssertionError as e:assert str(e)=='STREAM_SERIALIZER_OWNER_CHANGED'
else:raise AssertionError('changed serializer not detected')
r.restore(rt)
# Actual frozen module install twice, no plant and original stream implementation.
import study_common as sc,operational_memory_v3 as m
base=r.ensure(sc.rt,m);assert r.ensure(sc.rt,m) is base
assert base.__code__.co_filename=='<versioned streaming runtime artifact serializer>'
out=dict(status='PASS',cases=5,no_physics=True,no_original_serialization_schema_change=True,once_per_runtime_module=True,closure_reset=True,unexpected_owner_rejected=True)
(S/'output/STREAM_REUSE_LOCAL_REGRESSION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
