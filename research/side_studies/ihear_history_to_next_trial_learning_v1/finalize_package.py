"""Close and seal completed evidence, then copy byte-identically to the user's review folder."""
from pathlib import Path
import json,hashlib,time,shutil,sys,datetime
from final_audit import sha,read,put,P
R=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_history_to_next_trial_learning_v1')
REQUIRED=['REPORT.md','RESEARCH_BASELINE_AUDIT.md','CONTINUOUS_REPETITION_PROTOCOL.md','HISTORY_REPRESENTATION.md','ACTION_SPACE_CONTRACT.md',
    'DATASET_AND_SPLIT_AUDIT.md','ILC_STUDY.md','BAYESIAN_OPTIMIZATION_STUDY.md','HISTORY_VALUE_STUDY.md','CONTINUOUS_REPETITION_RESULTS.json',
    'LEARNING_RESULTS.json','VALIDATION_RESULTS.json','ATTEMPT_ACCOUNTING.json','NEXT_RESEARCH_DECISION.md']
def main():
    evidence=read('audit/FINAL_EVIDENCE_AUDIT.json');protected=read('audit/PROTECTED_CLOSEOUT.json');acc=read('ATTEMPT_ACCOUNTING.json');plan=read('RUN_PLAN.json')
    assert evidence['status']==protected['status']=='PASS'
    assert read('PHYSICS_STOP.json')['status']=='STOP' and read('OWNED_ACTIVE_PROCESS.json')['active'] is False
    assert protected['started_unix']>=read('PHYSICS_STOP.json')['unix'],'FINAL_PROTECTED_HASH_MUST_FOLLOW_PHYSICS_STOP'
    for n in REQUIRED:assert (P/n).is_file(),n
    # No writes to protected trees between their final full hash and this seal.
    for name,info in read('audit/HISTORY_AFTER.json').items():
        st=Path(name).stat();assert st.st_size==info['size'] and st.st_mtime_ns==info['mtime_ns'],name
    from bootstrap import git_snapshot
    final_git=git_snapshot();assert final_git==read('audit/GIT_BEFORE.json');put('audit/GIT_AT_SEAL.json',final_git)
    current={str(f) for root in [Path('/home/hank/coding/adaptive-traction-mpc-learning'),P.parent] for f in root.rglob('*') if f.is_file() and not f.is_relative_to(P) and '.git' not in f.parts}
    assert current==set(read('audit/HISTORY_BEFORE.json')),'PROTECTED_INVENTORY_CHANGED_AFTER_HASH'
    now=time.time();assert now<plan['hard_stop_unix']
    put('STATE.json',dict(phase='STOP',physics_starts=acc['starts'],physics_ends=acc['ends'],owned_pids=[],no_auto_resume=True,finished_unix=now,
        elapsed_seconds=now-plan['t0_unix'],reason='Preregistered experiments, independent recomputation and protection audit complete'))
    put('PACKAGE_VERIFICATION.json',dict(status='PASS',checked_unix=now,required_files=REQUIRED,
        complete_raw_recomputations=acc['total_recomputed_complete_tasks'],independent_recompute_failures=acc['independent_recompute_failures'],
        physics=dict(starts=acc['starts'],ends=acc['ends'],budget=80,closed=True,serial=True,new_native_steps=acc['total_new_native_steps'],stop_file='PHYSICS_STOP.json'),
        live_state_continuity='PASS',history_future_truth_isolation='PASS',patient_split_isolation='PASS',model_and_action_hash_identity='PASS',
        actual_command_and_receipt_ownership='PASS',native_motion_and_terminal_recompute='PASS',
        protected_history=dict(status='PASS',files=protected['files'],bytes=protected['bytes'],all_sha256_recomputed=True,differences=[],
            full_hash_started_unix=protected['started_unix'],full_hash_finished_unix=protected['finished_unix'],
            full_sha_recompute_after_physics_stop=True,size_mtime_and_inventory_unchanged_at_seal=True),
        git_state_unchanged=protected['git_identical'],owned_processes_active=[],
        elapsed_seconds=now-plan['t0_unix'],hard_stop_met=now<plan['hard_stop_unix'],
        review_directory=str(R),canonical_directory=str(P),
        verification_scope='Separate raw arithmetic, replay, hashes and source checks; same research agent, not external peer review',
        limitations=['DATA_LIMITED: three independent training patients','Deterministic scientific simulation, not clinical evidence',
            'P00 first fork failed before any new physics; preserved in ledger','P00R v2 bootstrap separate force cost not exported; native/time/commands retained',
            'V13, PPO/SAC, neural models and Bellman learning NOT_RUN',
            'Internal development LOO fits share the development scaler; not strict independent calibration. External validation/test remain excluded.'],
        manifest='EVIDENCE_MANIFEST.json',manifest_seal='DELIVERY_SEAL.json'))
    (P/'README_DELIVERY.md').write_text('''# 交付与复核

先读 REPORT.md，再查 PACKAGE_VERIFICATION.json。完整证据同时保存在本 Windows 文件夹和 ENVIRONMENT.json 指向的 WSL canonical 文件夹。

EVIDENCE_MANIFEST.json 对本包除临时缓存、manifest/seal 自身外的每个证据文件保存 SHA256 和大小；DELIVERY_SEAL.json 封存 manifest。原始 trace/native/receipt、失败、模型权重和版本代码全部保留。镜像中原始 provenance 的绝对路径仍指向原 WSL canonical，未为迁移而改写历史证据。

用 Python 3.9+ 运行 verify_package.py 可只读校验整个 Windows 或 WSL 封存包，不需要 MuJoCo 或其他依赖，不产生新文件或 physics。

如需重新计算而非仅核对 SHA，可在保留封存原件后，在原 WSL 环境的另一个审计副本中运行 analyze_study.py --independent、final_audit.py 和 make_figures.py；这些脚本会刷新派生报告或审计时间戳，原始 provenance 的绝对路径仍指向 canonical 数据。不要运行 physics 入口继续本包；PHYSICS_STOP.json 已阻止新 START。若需另一次研究，应另建版本化研究包，不能覆盖本次结果。
''')
    excluded={'EVIDENCE_MANIFEST.json','DELIVERY_SEAL.json','MIRROR_VERIFICATION.json'}
    files={}
    for f in sorted(P.rglob('*')):
        rel=f.relative_to(P)
        if not f.is_file() or rel.parts[0]=='tmp' or '__pycache__' in rel.parts or str(rel) in excluded:continue
        files[str(rel)]=dict(size=f.stat().st_size,sha256=sha(f))
    put('EVIDENCE_MANIFEST.json',dict(schema='full_new_study_evidence_v1',files=files,excluded=['tmp/','__pycache__/',*sorted(excluded)],created_unix=time.time()))
    put('DELIVERY_SEAL.json',dict(manifest_sha256=sha(P/'EVIDENCE_MANIFEST.json'),package_verification_sha256=sha(P/'PACKAGE_VERIFICATION.json'),
        report_sha256=sha(P/'REPORT.md'),files=len(files),bytes=sum(x['size'] for x in files.values()),sealed_unix=time.time()))
    assert R.resolve()==Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/ihear_history_to_next_trial_learning_v1').resolve()
    for i,rel in enumerate([*files,'EVIDENCE_MANIFEST.json','DELIVERY_SEAL.json']):
        source=P/rel;dest=R/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        expected=files.get(rel,{}).get('sha256') or sha(source)
        assert sha(dest)==expected,'MIRROR_CORRUPT:'+rel
        if i%500==0:print('MIRROR_VERIFIED',i,len(files),flush=True)
    verification=dict(status='PASS',files=len(files),all_evidence_bytes_verified=True,completed_unix=time.time(),manifest_sha256=sha(R/'EVIDENCE_MANIFEST.json'))
    put('MIRROR_VERIFICATION.json',verification);shutil.copy2(P/'MIRROR_VERIFICATION.json',R/'MIRROR_VERIFICATION.json')
    print('SEALED_AND_MIRRORED',len(files),sum(x['size'] for x in files.values()),flush=True)
if __name__=='__main__':main()
