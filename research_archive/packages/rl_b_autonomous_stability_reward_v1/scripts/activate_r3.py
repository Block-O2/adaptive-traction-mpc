"""Activate exactly one pre-audited optional Reward; never launch training."""
from pathlib import Path
import argparse,json,os,runpy,shutil,time
from research_common import ROOT,NO_TRAIN,RESERVATION,read,atomic,sha,now,same_pid,check_resources,decision


def inspect():
    draft=ROOT/'drafts/R3_unit30/rewards.py';prior=read(ROOT/'audit/R3_REWARD_PRETRAIN_AUDIT.json',{})
    ledger=read(ROOT/'LEDGER.json');q=read(ROOT/'followup_queues/H2_RETENTION_TO060_v1/START.json',{})
    end=read(ROOT/'followup_queues/H2_RETENTION_TO060_v1/END.json',{})
    active=[]
    for p in (ROOT/'owned').glob('*.json'):
        x=read(p)
        if same_pid(x.get('worker')):active.append(x['job'])
    outstanding=sum(a['reserved_native_steps'] for a in ledger['attempts'] if not a['settled'])
    expected_old=read(ROOT/'REWARD_VERSION_MANIFEST.json')['source_sha256']
    cfgplan=read(ROOT/'configs/R3_UNIT_SCREEN10_PLAN_v1.json')
    checks=dict(H2_queue_complete=end.get('status')=='COMPLETE',H2_supervisor_exited=not same_pid(q.get('identity')),
        H2_two_parent_result=read(ROOT/'RETENTION_H2_RESULTS.json',{}).get('status')=='COMPLETE_BOUNDED_RETENTION_COHORT',
        H2_seven_question_reflection=(ROOT/'H2_RETENTION_REFLECTION.md').is_file(),
        no_live_worker=not active,no_open_native_reservations=not outstanding,
        draft_math_audit=prior.get('status')=='PASS' and prior.get('candidate_source_sha256')==sha(draft),
        current_source_matches_prior_manifest=sha(ROOT/'scripts/rewards.py')==expected_old,
        exactly_R0_R1_R2_before_activation=set(read(ROOT/'REWARD_VERSION_MANIFEST.json')['versions'])=={'R0','R1','R2'},
        R3_not_already_registered=not (ROOT/'reward_versions/R3').exists(),
        future_source_binding=cfgplan['required_sources']['rewards.py']==sha(draft),
        training_cap=ledger['training_attempts']+20<=450,
        evaluation_cap_including_final8=ledger['evaluation_attempts']+4+8<=60,
        native_cap_including_final8=ledger['native_steps']+outstanding+32*RESERVATION<=50000000,
        at_least_two_hours_before_no_training=NO_TRAIN-time.time()>7200,
        no_closing=not (ROOT/'STOP_REQUESTED').exists() and not (ROOT/'END.json').exists())
    return dict(time_utc=now(),ready=all(checks.values()),checks=checks,active_workers=active,
        outstanding_native=outstanding,prior_source_sha256=expected_old,candidate_sha256=sha(draft),
        maximum_new_native_with_final8=32*RESERVATION,remaining_new_training_seconds=NO_TRAIN-time.time())


def activate():
    inspection=inspect();assert inspection['ready'],'R3_ACTIVATION_PRECONDITION:'+json.dumps(inspection)
    check_resources();draft=ROOT/'drafts/R3_unit30/rewards.py'
    oldmanifest=read(ROOT/'REWARD_VERSION_MANIFEST.json');oldsha=sha(ROOT/'REWARD_VERSION_MANIFEST.json')
    archived=ROOT/'audit/reward_manifest_versions'/f'REWARD_VERSION_MANIFEST_{oldsha}.json';archived.parent.mkdir(exist_ok=True)
    if archived.exists():assert sha(archived)==oldsha
    else:shutil.copyfile(ROOT/'REWARD_VERSION_MANIFEST.json',archived)
    oldaudit=ROOT/'audit/R3_REWARD_PRETRAIN_AUDIT.json';archive=ROOT/'audit/reward_scale_audit_versions'/f'DRAFT_{sha(oldaudit)}.json';archive.parent.mkdir(exist_ok=True);shutil.copyfile(oldaudit,archive)
    source_dir=ROOT/'source_versions'/('before_R3_'+sha(ROOT/'scripts/rewards.py'));source_dir.mkdir(exist_ok=True);shutil.copyfile(ROOT/'scripts/rewards.py',source_dir/'rewards.py')
    versions=runpy.run_path(str(draft))['VERSIONS'];assert all(versions[k]==oldmanifest['versions'][k] for k in ['R0','R1','R2'])
    directory=ROOT/'reward_versions/R3';directory.mkdir()
    shutil.copyfile(draft,directory/'reward.py')
    selected=dict(id='R3',parameters=versions['R3'],finite_task_gamma=1.,uniform_units_divisor=30.,
        source_selection='transition(version=id,...) in this exact module',original_R0_contract='runtime/pilot_env.py',
        parent_critic_and_Adam='Restore original successful050 without unit rescaling; intentional optimizer/value/GAE unit-coupling ablation')
    atomic(directory/'SELECTED_CONFIG.json',selected)
    definition=dict(id='R3',complete_source_sha256=sha(directory/'reward.py'),selected_config_sha256=sha(directory/'SELECTED_CONFIG.json'),
        complete_source_path='reward_versions/R3/reward.py',selected_config_path='reward_versions/R3/SELECTED_CONFIG.json')
    atomic(directory/'DEFINITION.json',definition)
    temporary=ROOT/'scripts'/f'rewards.py.activate.{os.getpid()}'
    shutil.copyfile(draft,temporary);os.replace(temporary,ROOT/'scripts/rewards.py')
    assert sha(ROOT/'scripts/rewards.py')==inspection['candidate_sha256']
    from audit_r3_reward_units import audit
    validated=audit(ROOT/'scripts/rewards.py');assert validated['status']=='PASS' and validated['active_candidate']
    auditpath=ROOT/'audit/R3_REWARD_ACTIVATED_AUDIT.json';shutil.copyfile(ROOT/'audit/R3_REWARD_PRETRAIN_AUDIT.json',auditpath)
    manifest=dict(oldmanifest)
    manifest.update(status='VERSIONED_FORMULAS_TRAINING_STATUS_IN_RESULTS',source_sha256=sha(ROOT/'scripts/rewards.py'),versions=versions,
        registered_utc=now(),previous_manifest_sha256=oldsha,previous_manifest_archive=str(archived.relative_to(ROOT)),
        identity_scope='Original R0/R1/R2 definitions remain immutable. Added R3 has an independent exact full-source/config definition. Actual per-job implementations remain source-bound.',
        active_module_implementation_equivalence=dict(from_source_sha256=inspection['prior_source_sha256'],to_source_sha256=inspection['candidate_sha256'],
             unchanged_versions=['R0','R1','R2'],audit_path=str(auditpath.relative_to(ROOT)),audit_sha256=sha(auditpath)))
    manifest['definition_identities']={**oldmanifest['definition_identities'],'R3':dict(**definition,definition_sha256=sha(directory/'DEFINITION.json'),definition_path='reward_versions/R3/DEFINITION.json')}
    atomic(ROOT/'REWARD_VERSION_MANIFEST.json',manifest)
    registry=read(ROOT/'ADDITIONAL_REWARD_STUDIES.json',dict(version='BOUNDED_ADDITIONAL_REWARD_STUDIES_v1',studies=[]))
    assert not any(x['reward']=='R3' for x in registry['studies'])
    registry['studies'].append(dict(reward='R3',study_id='R3_UNIT_SCREEN10_v1',status='PLANNED',result_path='R3_REWARD_RESULTS.json',
        plan='configs/R3_UNIT_SCREEN10_PLAN_v1.json',planned_training=20,planned_frozen=4,source_sha256=inspection['candidate_sha256']))
    registry['time_utc']=now();atomic(ROOT/'ADDITIONAL_REWARD_STUDIES.json',registry)
    with (ROOT/'REWARD_CANDIDATES.md').open('a') as f:
        f.write('\n\n## R3：R1整体单位除30（实际激活，尚未训练）\n\n激活UTC：'+now()+'。只测试这一尺度；30来自abs(failure15)+floor15，未使用最终未见结果。所有progress、success/failure、force、moment、variation及failure floor统一除30；gamma1、失败potential0、成功3规则不变。完整轨迹奖励偏好不变，旧critic/Adam不重标定，因此真实PPO更新可能不同。局部梯度不能预测任务完成或长期保持。\n\n参数：\n\n```json\n'+json.dumps(versions['R3'],ensure_ascii=False,indent=2)+'\n```\n\n从两个共同原050恢复，LR3e-4、aggregate64及全局终末30协议不变；最多各10集和mean/sample dev1各一次。训练与原评价Reward身份分开，所有失败保留，最终8次动作流仍未打开。R0/R1/R2原定义和完整源码继续保存，新完整模块对它们的输出逐项相同，证据见audit/R3_REWARD_ACTIVATED_AUDIT.json。\n')
    level=read(ROOT/'audit/DEVELOPMENT_LEVEL_A.json');level.setdefault('subsequent_affected_version_checks',[]).append(dict(time_utc=now(),
        affected_change='Add one positive uniform R1/30 unit ablation; original R0/R1/R2 output equivalence checked on saved and random inputs',
        reward_source_sha256=inspection['candidate_sha256'],pretrain_audit='audit/R3_REWARD_ACTIVATED_AUDIT.json',pass_=True,
        new_physics_for_checks=0,new_Adam_for_checks=0,existing_447_runtime_and_truth_firewall_tests_reused=True));atomic(ROOT/'audit/DEVELOPMENT_LEVEL_A.json',level)
    record=dict(time_utc=now(),status='ACTIVATED_NOT_TRAINED',inspection=inspection,activation_source_sha256=sha(Path(__file__)),
        definition_sha256=sha(directory/'DEFINITION.json'),manifest_sha256=sha(ROOT/'REWARD_VERSION_MANIFEST.json'),
        original_manifest_sha256=oldsha,audit_sha256=sha(auditpath),new_physics=0,new_Adam=0)
    atomic(ROOT/'audit/R3_ACTIVATION.json',record)
    decision('R3_SOURCE_ACTIVATED_AND_PRETRAIN_AUDITED',record,'Freshly validate and launch only the sealed R3 two-parent10 finite plan; no automatic reward generation or final Campaign',
        hypotheses_accepted=['Uniform reward-unit scaling is a justified single ablation of old-critic/GAE/joint-clip/Adam coupling'],
        hypotheses_rejected=['Small initial actor gradient alone predicts actual Adam drift','Adding R3 changes original R0/R1/R2 reward outputs','Pretrain arithmetic PASS predicts task or retention success'])
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--activate',action='store_true');a=p.parse_args()
    print(json.dumps(activate() if a.activate else inspect()))
