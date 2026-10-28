from pathlib import Path
import datetime, hashlib, importlib.metadata, json, os, platform, shutil, subprocess, time

root = Path('/home/hank/ihear-lab')
origin = root / 'constraint_geometry_learning_v4'
package = root / 'smoothness_critic_research_v5'
if package.exists():
    package = root / ('smoothness_critic_research_v5_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
package.mkdir(exist_ok=False)
for name in ['audit', 'source', 'legacy_source', 'runtime', 'analysis', 'experiments', 'jobs', 'owned', 'logs', 'attempts', 'predictions', 'history', 'figures', 'models', 'queue']:
    (package / name).mkdir()
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024**2), b''): h.update(block)
    return h.hexdigest()
def put(name, obj):
    p = package/name; p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')
journal = root/'RESEARCH_DECISION_JOURNAL.md'
before = journal.read_bytes()
put('audit/JOURNAL_BEFORE.json', dict(size=len(before), sha256=hashlib.sha256(before).hexdigest()))
now = time.time(); dt=datetime.datetime.fromtimestamp(now, datetime.timezone.utc)
activation=dict(id=package.name+'_'+dt.strftime('%Y%m%dT%H%M%SZ'), package=str(package), T0_UTC=dt.isoformat(), T0_Asia_Shanghai=dt.astimezone(datetime.timezone(datetime.timedelta(hours=8))).isoformat(), t0_unix=now, hard_stop_unix=now+36000, deadline_UTC=datetime.datetime.fromtimestamp(now+36000, datetime.timezone.utc).isoformat(), deadline_Asia_Shanghai=datetime.datetime.fromtimestamp(now+36000, datetime.timezone(datetime.timedelta(hours=8))).isoformat(), state='ACTIVATED', maximum_hours=10, historical_guard='READ_ONLY_ORIGINAL', no_automatic_next_round=True)
put('ACTIVATION.json',activation); put('START.json',activation)
review_marker='Constraint Geometry & Learning v4 流程回顾'
with journal.open('a') as f:
    if review_marker not in before.decode():
        review='上一轮开始、结束和技术缺口已记录，但未明确说明提前结束的流程问题。日志结束条目距ACTIVATION约1.43小时，最终END封包约1.50小时，并非授权的10小时。双端点仅点态等价，采样间和最终actuator保护未闭合；替代guard物理、同权限优化收益、独立Learning及PPO增量均未运行或未建立。六个局部点吻合与force/moment取舍不能替代这些分支。后续采用动态队列，某分支受阻或一次实验结束后继续评估其它有信息价值的方向；也不为耗时重复计算。'
        f.write('\n\n---\n\n## '+dt.isoformat()+' UTC — '+review_marker+'\n\n'+review+'\n')
    f.write('\n\n---\n\n## '+dt.isoformat()+' UTC — Smoothness-Aware Control & Long-Horizon Critic v5 开始 ['+activation['id']+']\n\n本轮优先验证实际Human运动和cuff施力平顺性：比较强固定、参考平顺化及原guard完整生效下的提前协调，保留完整任务、原motion门和所有失败。随后以相同决策及剩余完整任务费用检验短视；仅在有真实排序或决策缺口时开展长期Critic及Learning增量。动态队列按吞吐、证据与剩余预算调整；T0起最多10小时，截止不重置。所有新源码和raw隔离，历史只读，最终核验并STOP。\n')
    f.flush(); os.fsync(f.fileno())
put('STATUS.json',dict(state='RECOVERING',activation=activation['id'],updated_UTC=dt.isoformat()))
put('runtime/RUN_PLAN.json',dict(t0_unix=now,hard_stop_unix=now+36000,physics_hard_stop_unix=now+33600,dispatch_cutoff_unix=now+32700,validation_dispatch_cutoff_unix=now+32700,no_new_physics_after_unix=now+32700,physical_timeout_s=300,physics_budget=500,native_step_cap=50000000,development_cap=360,seed=2026102305,all_physics_serial=True,min_ram_gib=6,min_disk_gib=18,allocation='DYNAMIC; no commitment to exhaust caps'))
put('audit/RECOVERY_SCOPE.json',dict(request_truncated_after='传统分支感知模型指导的',continuation_requested=True,read_only_roots=[str(root/x) for x in ['constraint_geometry_learning_v4','representation_execution_v3','autonomous_coordination_learning_v2','learning_guided_motion_improvement_v1']],missing_requested_roots=['force_motion_coupling_diagnosis_v2','force_mechanism_waypoint_v3'],fallback_root=str(root/'rl_b_matched_recovery_stability_v1/github/research/side_studies')))
environment=dict(platform=platform.platform(),python=platform.python_version(),cpu_count=os.cpu_count(),dependencies={})
for name in ['numpy','scipy','mujoco','torch','scikit-learn','gymnasium','matplotlib']:
    try: environment['dependencies'][name]=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: environment['dependencies'][name]='not in system python metadata'
put('audit/ENVIRONMENT.json',environment)
put('audit/PROCESSES_AT_ACTIVATION.json',dict(processes=subprocess.check_output(['ps','-eo','pid,ppid,lstart,etime,args'],text=True)))
for name in ['source','legacy_source']:
    shutil.copytree(origin/name,package/name,dirs_exist_ok=True)
for name in ['code','control','deps']:
    shutil.copytree(origin/'runtime'/name,package/'runtime'/name)
shutil.copytree(origin/'runtime/source',package/'runtime/source',ignore=shutil.ignore_patterns('results','__pycache__','.git','*.pyc'))
for name in ['output','reports','motion_series','tmp']:(package/'runtime'/name).mkdir()
for name in ['FROZEN_18D.json','MOTION_ACCEPTANCE_PROTOCOL.json','PARAMETER_MAP.json','ACTION_SET.json']:
    shutil.copy2(origin/'runtime'/name,package/'runtime'/name)
shutil.copy2(origin/'runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json',package/'runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json')
relocations=[]
for folder in ['source','legacy_source','runtime/code','runtime/control','runtime/deps','runtime/source']:
    for file in (package/folder).rglob('*'):
        if file.is_file() and file.suffix in ['.py','.json','.toml','.yaml','.yml','.xml','.md']:
            try: old=file.read_text()
            except UnicodeDecodeError: continue
            new=old.replace(str(origin),str(package)).replace(str(root/'representation_execution_v3'),str(package)).replace(str(root/'autonomous_coordination_learning_v2'),str(package))
            if old!=new: file.write_text(new);relocations.append(str(file.relative_to(package)))
put('audit/CLOSURE_RELOCATION.json',dict(origin=str(origin),destination=str(package),origin_manifest_sha256=sha(origin/'OUTPUT_MANIFEST.json'),exact_root_relocations=relocations))
protected={}
for directory in ['constraint_geometry_learning_v4','representation_execution_v3','autonomous_coordination_learning_v2','learning_guided_motion_improvement_v1','rl_b_autonomous_stability_reward_v1']:
    base=root/directory
    for f in base.rglob('*'):
        if f.is_file() and '__pycache__' not in f.parts and '.git' not in f.parts:
            st=f.stat();protected[str(f)]=dict(size=st.st_size,mtime_ns=st.st_mtime_ns)
put('audit/PROTECTED_METADATA_BEFORE.json',dict(files=protected))
put('audit/HISTORICAL_MANIFEST_IDENTITIES.json',{name:{f:sha(root/name/f) for f in ['OUTPUT_MANIFEST.json','PACKAGE_VERIFICATION.json','END.json'] if (root/name/f).is_file()} for name in ['constraint_geometry_learning_v4','representation_execution_v3','autonomous_coordination_learning_v2','learning_guided_motion_improvement_v1']})
repo=root/'rl_b_matched_recovery_stability_v1/github'
put('audit/GIT_BEFORE.json',dict(repo=str(repo),HEAD=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),status=subprocess.check_output(['git','-C',str(repo),'status','--porcelain','--untracked-files=no'],text=True)))
Path('/tmp/ihear_v5_active_package').write_text(str(package))
print(json.dumps(activation,ensure_ascii=False,indent=2))
print('COPIED_AND_ACTIVATED',package,'protected_files',len(protected),'relocated_files',len(relocations))
