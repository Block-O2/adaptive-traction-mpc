"""Install original streaming serializer once; no previous run closure survives."""
BASE={}
def ensure(rt,memory):
 if rt not in BASE:
  memory.install(rt);BASE[rt]=rt.persist_runtime_artifacts
 else:
  assert rt.persist_runtime_artifacts is BASE[rt],'STREAM_SERIALIZER_OWNER_CHANGED'
 return BASE[rt]
def restore(rt):
 assert rt in BASE
 rt.persist_runtime_artifacts=BASE[rt]
