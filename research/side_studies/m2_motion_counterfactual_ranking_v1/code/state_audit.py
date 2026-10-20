from common import *
snaps=[]
for p in sorted((MATRIX/'output').glob('*_SNAPSHOT.json')):
 j=load(p); fields=[];hashed=[]
 def walk(x,path=''):
  if isinstance(x,dict):
   if 'sha256' in x or 'streaming_full_rows_sha256' in x: hashed.append(path)
   for k,v in x.items():fields.append(path+'.'+k);walk(v,path+'.'+k)
  elif isinstance(x,list):
   for i,v in enumerate(x[:3]):walk(v,path+'.'+str(i))
 walk(j)
 snaps.append(dict(path=str(p),sha256=sha(p),snapshot_hash=j['hash'],branch_kind=j.get('branch_kind'),native_state_count=j.get('native_state_count'),opaque_handles=j.get('opaque_fork_preserved'),hash_only_array_count=len(hashed),hash_only_fields=hashed,component_presence={k:any(k in s for s in fields) for k in ['native_integration','updater','observer','reference_state','reference_governor','planner','lifecycle','pending','python_rng','numpy_rng']},interface_state=j.get('interface_state'),saved_state_class='NON_RESTORABLE_FINGERPRINT',original_fork_class='COMPLETE_PROCESS_SCOPED_FORK'))
gate=load(MATRIX/'BRANCH_GATE.json')
sourcefiles=[MATRIX/'code/native_data.py',MATRIX/'deps/fork_core.py',MATRIX/'code/interfaces.py',MATRIX/'code/native_core.py',MATRIX/'PROTOCOL.json']
text={str(p):p.read_text() for p in sourcefiles}
assert 'os.fork()' in text[str(sourcefiles[0])]
assert "sha256(x.tobytes())" in text[str(sourcefiles[1])]
assert "process-scoped only" in text[str(sourcefiles[1])]
# Inventory candidates for durable checkpoint files; never load any executable object.
checkpoint_files=[str(p) for p in MATRIX.rglob('*') if p.is_file() and p.suffix.lower() in ['.pkl','.pickle','.ckpt','.dmp','.core']]
process=subprocess.run(['ps','-eo','pid,ppid,etimes,args'],capture_output=True,text=True).stdout
md('PROCESS_INVENTORY_BEFORE.txt',process)
save('STATE_RESTORATION_AUDIT.json',dict(status='NOT_EVALUABLE_NEW_FORK',stage_C='STOPPED_AT_RESTORATION_GATE',historical_gate=gate,snapshots=snaps,durable_checkpoint_files=checkpoint_files,source_evidence=[dict(path=str(p),sha256=sha(p)) for p in sourcefiles],reason='Fork copied the entire live process, including opaque handles; JSON replaces integration vectors, estimator arrays, RNG ndarray and histories by hashes. No durable reload checkpoint or still-live parent process was found. Rebuilding Human/plant to regenerate prefixes is forbidden by this task.',historical_label_contract='SCIENTIFIC_SIMULATION, native physical certificates and simulation-version lineage; not REALTIME_VALIDATED 100ms wall expiry or 40ms host bridge qualification',new_branch_attempts=0,approximate_replay_attempts=0,forbidden='q/dq-only reconstruction or fingerprint stitching'))
md('STATE_RESTORATION_AUDIT.md',f'''# 状态恢复审计

新增合法 fork：**NOT_EVALUABLE**。阶段 C 停止，新增 branch attempts=0。

原完整 fork 与磁盘摘要必须区分。`native_data.py` 在 CPU 单线程静止状态调用 `os.fork()`，fork 前后校验完整 manifest digest，并等待每个 child；原 BRANCH_GATE 保存两条零残余 full trace 逐字段差为0、parent hash不变证据。该证据支持历史进程内合法反事实，不支持本轮从JSON恢复。

共审计 {len(snaps)} 个 snapshot 文件。`fork_core.state_manifest` 将 ndarray、MuJoCo integration state、长历史列表变成 SHA256/shape/dtype；opaque locks和native cache handles仅标注fork_preserved。JSON包含q/dq相关状态、estimator/commissioning、reference/phase、planner、mask/carry/count、lifecycle/pending、RNG等摘要，但缺少完整数组内容、对象关系的可执行恢复及native handles。仅q/dq不能补齐这些状态。

未找到durable checkpoint；任务开始进程清单没有存活的历史父进程或重型物理实验。没有重建plant/Human、拼接snapshot或尝试近似replay。历史合法fork、当前不可恢复摘要、近似replay三个类别分别记录；第三类本轮0次。

历史执行模式为SCIENTIFIC_SIMULATION。其物理安全与simulation-version因果检查可用于有限committed标签；原raw scorer的wall plan_age FAIL仍保留，mode-aware realtime结果为N/A。本轮不将它改写为40ms bridge/100ms wall lifecycle的host合格执行。不能进入相同state下V_replan对照。

后续只读取已完成分支与dense native原始证据；所有source/hash、component字段与原BRANCH_GATE原文在JSON。
''')
print('STATE_GATE_STOP',len(snaps),len(checkpoint_files),flush=True)
