from pathlib import Path
import os, json, time, hashlib, subprocess, shutil, datetime
SIDE=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')
MAIN=Path('/home/hank/coding/adaptive-traction-mpc-learning')
REVIEW=Path(__file__).resolve().parents[1]; P=SIDE/REVIEW.name
A=SIDE/'m2_18d_early_return_motion_repair_v1'
assert not P.exists(), 'Never overwrite an existing study'
P.mkdir()
for d in ['audit','analysis','control','logs','reports','derived','figures','output','motion_series','tmp','provenance']:(P/d).mkdir()
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as src:
  for b in iter(lambda:src.read(2**20),b''):h.update(b)
 return h.hexdigest()
def git():
 env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
 return {n:subprocess.check_output(['git','-C',str(MAIN),*args],env=env).decode() for n,args in [('head',['rev-parse','HEAD']),('branch',['branch','--show-current']),('status',['status','--porcelain=v1','--untracked-files=all']),('cached',['diff','--cached','--binary']),('unstaged',['diff','--binary'])]}
t0=datetime.datetime.fromisoformat('2026-10-18T15:55:26+08:00').timestamp()
put('RUN_PLAN.json',dict(t0='2026-10-18T15:55:26+08:00',t0_unix=t0,hard_stop_unix=t0+21600,no_new_physics_after_unix=t0+18900,dispatch_cutoff_unix=t0+18900,physics_hard_stop_unix=t0+18900,physical_timeout_s=900,physics_budget=60,development_cap=42,validation_reserved=18,all_physics_serial=True,no_training=True))
put('ENVIRONMENT.json',dict(canonical=str(P),review=str(REVIEW),python='/home/hank/envs/adaptive-online-rl-v1/bin/python',historical_source=str(A),created_unix=time.time(),distribution=os.environ.get('WSL_DISTRO_NAME')))
put('STATE.json',dict(phase='READ_ONLY_AUDIT',next='Complete all-track historical audit and terminal native quantification before candidate selection',physics_starts=0))
put('audit/GIT_BEFORE.json',git());protected={}
print('Protection snapshot started',flush=True)
for root in [MAIN,SIDE]:
 for f in sorted(root.rglob('*')):
  if not f.is_file() or f.is_relative_to(P) or '.git' in f.parts:continue
  st=f.stat();protected[str(f)]={'size':st.st_size,'mtime_ns':st.st_mtime_ns,'sha256':sha(f)}
put('audit/HISTORY_BEFORE.json',protected);checks=[]
for name in ['m2_18d_early_return_motion_repair_v1','m2_18d_w1_d_qualification_v1','m2_18d_t_second_round_coordination_v1','m2_18d_terminal_expanded_prefix_validation_v1']:
 root=SIDE/name
 for mn in ['EXECUTION_CODE_MANIFEST.json','EVIDENCE_MANIFEST.json']:
  obj=json.loads((root/mn).read_text());errors=[]
  for rel,entry in obj['files'].items():
   f=Path(rel) if Path(rel).is_absolute() else root/rel;expected=entry if isinstance(entry,str) else entry['sha256']
   if not f.exists() or sha(f)!=expected:errors.append(str(f))
  checks.append(dict(study=name,manifest=mn,count=len(obj['files']),errors=errors,sha256=sha(root/mn)))
put('audit/HISTORICAL_MANIFESTS_VERIFIED.json',checks);assert not any(x['errors'] for x in checks)
for d in ['source','code','deps','weights']:shutil.copytree(A/d,P/d,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
rebased=[]
for d in ['source','code','deps','weights']:
 for f in (P/d).rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:s=f.read_text()
   except UnicodeError:continue
   if str(A) in s:f.write_text(s.replace(str(A),str(P)));rebased.append(str(f.relative_to(P)))
for n in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json','FROZEN_SELECTION.json','SELECTION_RULE.json']:shutil.copy2(A/n,P/n)
shutil.copy2(A/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',P/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
for n in ['base_campaign.py','round_planner.py','interface_base.py','independent_recompute.py','owner.py','early_return_planner.py']:shutil.copy2(A/'control'/n,P/'control'/n)
shutil.copy2(REVIEW/'control/bootstrap.py',P/'control/bootstrap.py')
shutil.copy2(MAIN/'AGENTS.md',P/'provenance/AGENTS.md')
shutil.copy2('/mnt/c/Users/HankL/.codex/attachments/81f62007-6cbf-4986-86bc-a25c5fdbf047/已粘贴的文本.txt',P/'provenance/USER_REQUEST.txt')
for n in ['REPORT.md','repair_PLAN.json','REPAIR_FROZEN_SELECTION.json','VALIDATION_RESULTS.json','EXECUTION_CODE_MANIFEST.json','EVIDENCE_MANIFEST.json','HOLDOUT_REGISTRATION.json','NEXT_RESEARCH_DECISION.md']:shutil.copy2(A/n,P/'provenance'/('early_return__'+n))
put('audit/PATH_REBASE.json',dict(path_only=rebased,source=str(A)))
(P/'MULTI_TRACK_DECISION_LOG.md').write_text('''# 多方向研究决策日志

T0：2026-10-18 15:55:26 +08:00。硬截止21:55:26；21:10:26前结束物理阶段，60 START上限，全部串行。预留18 START用于对照、重复和真正未见prefix验证；不要求耗尽预算。

## D0 — 建立证据全貌
先审查A终末响应、B状态可靠性、C真实运动平顺性、D力矩及跟踪代价、E执行与学习接口。以原native/receipt/metrics作只读分析，不重跑历史来替代数据阅读。
最新ER110_R4_120是失败研究候选，不能因降力升级。先量化真实终末overshoot，独立于excursion差。
所有新干预保留父候选参数；新名称/manifest/原证书/完整资格分别记录。A最多两个有机制依据的候选，随后停止或切换；不进行微小Waypoint盲搜。
冻结W2为有条件未见验证候选；需复核历史START。无开发合格方案则不消费验证。
正式B、历史代码/证据、plant、安全/因果链均只读；仅新独立包可写。单agent执行，最后使用分离计算复核，不声称独立人员审计。
''')
for f in [P/'ENVIRONMENT.json',P/'RUN_PLAN.json',P/'MULTI_TRACK_DECISION_LOG.md',P/'STATE.json']:shutil.copy2(f,REVIEW/f.name)
print(json.dumps(dict(status='PASS',protected_files=len(protected),checks=checks,seconds_since_T0=time.time()-t0)),flush=True)
