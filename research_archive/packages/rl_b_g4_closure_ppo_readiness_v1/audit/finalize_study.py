from pathlib import Path
import sys,json,hashlib,time,os,zipfile,datetime,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import ROOT,put
from checkpoints import contract,sha
old=ROOT.parent/'rl_b_cloud_g4_repair_v1';original=ROOT.parent/'rl_b_cloud_v1'
read=lambda p:json.loads(p.read_text())
names=['ppo_initial','ppo_resume','ppo_evaluation'];rs={n:read(ROOT/'runs'/n/'physics/RESULT.json') for n in names};aa={n:read(ROOT/'audit'/('PPO_'+n.removeprefix('ppo_').upper()+'_INDEPENDENT.json')) for n in names}
initial,resume,evaluation=[rs[n] for n in names]
assert all(a['pass'] for a in aa.values())
assert initial['update_pass'] and resume['update_pass'] and resume['resume']['pass'] and evaluation['resume']['pass']
assert len({r['pid'] for r in rs.values()})==3
plan=read(ROOT/'RUN_PLAN.json');envver=read(ROOT/'ENVIRONMENT_VERSION.json')
steps=[x for n in names[:2] for x in rs[n]['optimizer_steps']]
wall=sum(r['wall_s'] for r in rs.values());metrics=[r['episodes'][0]['info'] for r in rs.values()]
nds=sum(m['native_steps_total'] for m in metrics);tds=sum(m['task_native_steps'] for m in metrics);rls=sum(m['rl_decisions'] for m in metrics)
update={'status':'PASS','category':'UNQUALIFIED_TRAINING_SMOKE','seed':plan['seed'],'network_hidden_layers':[16,16],'physics_envs':1,'device':'cpu','ppo_train_calls':sum(len(r['updates']) for r in rs.values()),'actual_optimizer_gradient_steps':len(steps),'gradient_steps':steps,'ppo_collection_decisions':16,'audit_tail_decisions_not_used_by_optimizer':38,'frozen_evaluation_decisions':24,'all_real_rollout_decisions':rls,'real_native_physics_steps':nds,'task_native_physics_steps':tds,'episodes_completed':3,'frozen_task_evaluation_successes':int(evaluation['evaluation']['runtime_task_success']),'frozen_task_evaluation_total':1,'losses':{n:rs[n]['updates'] for n in names[:2]},'episodes':[{'run':n,'status':m['status'],'task_s':m['task_s'],'reward_parts':m['reward_totals'],'native_steps_total':m['native_steps_total'],'task_native_steps':m['task_native_steps'],'rl_decisions':m['rl_decisions'],'source_result':str(ROOT/'runs'/n/'physics/RESULT.json'),'independent_audit':str(ROOT/'audit'/('PPO_'+n.removeprefix('ppo_').upper()+'_INDEPENDENT.json'))} for n,m in zip(names,metrics)],'wall_seconds_inside_children':wall,'outer_guard_wall_seconds':sum(read(ROOT/'runs'/n/'END.json')['resources']['wall_s'] for n in names),'cpu_user_s':sum(r['cpu_user_s'] for r in rs.values()),'cpu_system_s':sum(r['cpu_system_s'] for r in rs.values()),'peak_single_process_rss_KiB':max(r['peak_rss_KiB'] for r in rs.values()),'minimum_available_RAM_GiB':min(read(ROOT/'runs'/n/'END.json')['resources']['minimum_available_GiB'] for n in names),'physical_rollout_decisions_per_wall_s':rls/wall,'native_steps_per_wall_s':nds/wall,'simulated_seconds_per_wall_second':nds*.00025/wall,'teacher_used':False,'learning_success_claim':False,'counter_semantics':{'SB3_n_updates':'PPO epoch counter: 0→1→2; each epoch has two actual optimizer steps','optimizer_steps':'instrumented optimizer.step calls, Adam per-parameter step counter 0→2→4','episodes_completed_checkpoint_field':'per-process physical episode count; cumulative count is reconstructed along immutable parent checkpoint links','SB3_episode_num':'0 at both checkpoints because terminal completion occurs in audit tails outside collect_rollouts; restored exactly','gradient_optimizer_steps_total_checkpoint_field':'sum of per-parameter Adam step counters (26 then52 for13 parameter tensors), NOT actual optimizer call count; use actual_optimizer_gradient_steps=4'},'qualification_scope':'software and observed execution only; full PPO task qualification not granted'}
put(ROOT/'PPO_UPDATE_RESULTS.json',update)
checkpointrows=[]
for n in names[:2]:
 base=ROOT/'runs'/n/'physics/checkpoints/final';m=read(base.with_suffix('.json'))
 checkpointrows.append({'run':n,'model_sha256':sha(base.with_suffix('.zip')),'rng_sha256':sha(base.with_suffix('.rng.pt')),'metadata_sha256':sha(base.with_suffix('.json')),'metadata':m,'content_hashes_match':sha(base.with_suffix('.zip'))==m['model_sha256'] and sha(base.with_suffix('.rng.pt'))==m['rng_sha256']})
resume_audit={'status':'PASS','initial_process_pid':initial['pid'],'resume_process_pid':resume['pid'],'evaluation_process_pid':evaluation['pid'],'distinct_processes':len({r['pid'] for r in rs.values()})==3,'initial_process_exited_before_resume':read(ROOT/'runs/ppo_initial/END.json')['unix']<read(ROOT/'runs/ppo_resume/START.json')['unix'],'resume_process_exited_before_evaluation':read(ROOT/'runs/ppo_resume/END.json')['unix']<read(ROOT/'runs/ppo_evaluation/START.json')['unix'],'full_state_restore':resume['resume'],'evaluation_restore':evaluation['resume'],'optimizer_step_counters_before_resume':initial['optimizer_steps'][-1]['optimizer_steps'],'optimizer_step_counters_after_resume':resume['optimizer_steps'][-1]['optimizer_steps'],'continued_real_rollout':resume['episodes'][0]['info']['native_steps_total']>0,'continued_optimizer_updates':resume['update_pass'],'checkpoints':checkpointrows,'physical_episode_progress':{'initial_local_completed':1,'resumed_local_completed':1,'cumulative_checkpoint_parent_chain_completed':2,'frozen_evaluation_completed':1,'total_new_episodes':3},'model_counter_semantics':update['counter_semantics'],'resume_semantics':'fresh physical episode, no simulator or partial PPO buffer restoration; collection counter8→16 and optimizer state preserved','not_bitwise_continuous_physics_claim':True}
assert all(x['content_hashes_match'] for x in checkpointrows)
put(ROOT/'CHECKPOINT_RESUME_AUDIT.json',resume_audit)
parities={n:read(old/'audit'/('PARITY_'+n+'.json')) for n in ['slow','maximal','random']}
put(ROOT/'EXECUTION_PARITY_AUDIT.json',{'status':'PASS','scope':'byte-identical task/physics/action/execution source plus reused exact nominal raw parity and3 new independent physical audits; not full matched qualification or host realtime','source_references':read(ROOT/'audit/CONTRACT_SOURCE_REFERENCES.json'),'parent_exact_raw_parity':parities,'new_raw_case_audits':{n:aa[n]['case']['checks'] for n in names},'new_actual_Human_motion':{n:aa[n]['case']['motion'] for n in names},'new_raw_force_phase_integrals':{n:aa[n]['force']['phases'] for n in names},'full_frozen_execution_gate':'FAIL','matched_19_03_random_regression':'FAIL','host_realtime':'NOT_EVALUABLE','certificate_admission_ownership_bypassed':False})
# Every physical process has an authoritative outer START before import/reset.
attempts=[]
for n in names:
 d=ROOT/'runs'/n;s=read(d/'START.json');e=read(d/'END.json');ep=d/'physics/env/episode_0001'
 attempts.append({'run':n,'START':s,'END':e,'episode_start':read(ep/'EPISODE_START.json'),'episode_end':read(ep/'EPISODE_END.json'),'RESULT':str(d/'physics/RESULT.json'),'complete':s['unix']<e['unix'] and e['returncode']==0 and e['child_joined'] and not e['error']})
put(ROOT/'ATTEMPT_ACCOUNTING.json',{'status':'PASS','physics_attempts':3,'physics_process_START':3,'physics_process_END':3,'physical_episodes':3,'episode_START':3,'episode_END':3,'PPO_optimizer_gradient_steps':4,'attempts':attempts,'unit_test_groups':{'G4_UNIT_RESULTS.json':19,'REPAIR_BOUNDARY_TESTS.json':10,'SAFETY_AUTHORITY_TESTS.json':6,'EXECUTION_CONTRACT_TESTS.json':6},'read_only_raw_audits':{'old_force_episodes':9,'new_case_force_motion_owner_episodes':3},'failed_scientific_episodes_retained':['ppo_resume:ABORTED at19.840s','ppo_evaluation:ABORTED at16.610s'],'infrastructure_failures':[],'diagnostic_failures':[{'command':'first sandboxed attachment read','error':'bwrap loopback RTM_NEWADDR Operation not permitted','recovery':'authorized read via tool escalation; no physics launched'},{'command':'contract discovery searches','error':'candidate paths absent; rg exit2','recovery':'actual file inventory and ZIP search; absent B/H150 full authority reported'},{'command':'early progress probes','error':'RESULT.json not yet present or no running process match','recovery':'waited for owned guard completion'}],'clock_note':'Outer START/END unix fields are authoritative wall time. Inner EPISODE_START unix is a misnamed perf_counter host_start value from the recording wrapper, not UTC; no wall-time claim is based on it. It records episode identity after commissioning; outer START predates all physics. Inner END unix is true UTC epoch. Raw native time stays independently audited.','parameter_manifest':'RUN_PLAN.json plus frozen source/config contract and config_snapshot.json per episode','hard_episode_cap':12,'all_attempts_closed':all(x['complete'] for x in attempts),'no_new_long_physics_after_cutoff':all(x['START']['unix']<plan['no_new_physics_after_unix'] for x in attempts)})
# Preserve and verify all prior artifacts and original archive.
protected=read(ROOT/'audit/protected_before.json');mismatches=[]
for filename,expected in protected.items():
 p=Path(filename)
 if not p.exists() or sha(p)!=expected:mismatches.append(filename)
sourcefiles=[p for p in (ROOT/'source').rglob('*') if p.is_file()];sourcemap={str(p.relative_to(ROOT)):sha(p) for p in sourcefiles}
put(ROOT/'SOURCE_MANIFEST.json',{'files':sourcemap,'all_byte_identical_to_parent':all(sha(old/n)==h for n,h in sourcemap.items()),'source_count':len(sourcemap)})
archive=Path('/home/hank/ihear_rl_b_cpu_cloud_v1.zip');zipbad=[]
with zipfile.ZipFile(archive) as z:
 manifest=read(original/'SHA256_MANIFEST.json')['files']
 for n,rec in manifest.items():
  if hashlib.sha256(z.read(n)).hexdigest()!=rec['sha256']:zipbad.append(n)
 zipcrc=z.testzip()
# Inspect only own process IDs, never signal other work.
owned_pids=[r['pid'] for r in rs.values()]+[a['START']['pid'] for a in attempts]
alive=[pid for pid in owned_pids if Path(f'/proc/{pid}').exists()]
ownerends=[a['episode_end'] for a in attempts]
put(ROOT/'PROCESS_EXIT_AUDIT.json',{'status':'PASS' if not alive and all(e['owner_joined'] for e in ownerends) else 'FAIL','owned_pids':owned_pids,'owned_pids_still_alive':alive,'native_owners_joined':all(e['owner_joined'] for e in ownerends),'captures_cleared':all(e['capture_cleared'] for e in ownerends),'executors_closed':all(a['case']['checks']['executor_closed'] for a in aa.values()),'foreign_processes_signalled':False})
readiness=read(ROOT/'READINESS.json');gatekeys=['G4_TERMINATION_REWARD_PASS','RL_EXECUTION_CONTRACT_PASS','RL_TASK_REACHABILITY_PASS'];gateclosed=not all(readiness.get(k)=='PASS' for k in gatekeys)
qualification={'FORCE_INTEGRATION_PASS':'PASS','RUNTIME_TASK_COMPLETE_PASS':'PASS','MATCHED_TASK_EVALUATION_PASS':'FAIL','G4_STRICT_PASS':'FAIL','G4_TEST_HARNESS_COVERAGE':'PASS','EXECUTION_PARITY_PASS':'PASS','PPO_UPDATE_SMOKE_PASS':'PASS','CHECKPOINT_RESUME_PASS':'PASS','PPO_TASK_SUCCESS':'PASS' if evaluation['evaluation']['runtime_task_success'] else 'FAIL','PPO_FULL_QUALIFIED':'FAIL','TRAINING_PILOT_READY':'FAIL'}
put(ROOT/'QUALIFICATION_RESULTS.json',{'results':qualification,'scope':{'RUNTIME_TASK_COMPLETE_PASS':'historical20.165s random and complete nominal episodes only; not all policies','MATCHED_TASK_EVALUATION_PASS':'deployed frozen19.030±.050 regression fails; formal B/H150 sufficient contract NOT_EVALUABLE','G4_TEST_HARNESS_COVERAGE':'41 protocol/source tests; natural gaps retained','EXECUTION_PARITY_PASS':'observed nominal original source/raw parity and independent new execution checks','PPO_TASK_SUCCESS':'one frozen deterministic checkpoint evaluation,0/1 success','CHECKPOINT_RESUME_PASS':'optimizer/RNG/SB3 counters restored in distinct process and actual optimizer2→4; fresh physical episode semantics'},'formal_B_H150_full_contract':'NOT_EVALUABLE','formal_training_gate_remains_closed':gateclosed})
assert gateclosed and not mismatches and not zipbad and zipcrc is None and not alive
verification={'status':'PASS','scientific_qualification_all_passed':False,'historical_files_protected':len(protected),'historical_missing_or_mismatched':mismatches,'original_ZIP_sha256':sha(archive),'original_ZIP_unchanged':sha(archive)==protected[str(archive)],'ZIP_manifest_payloads_checked':len(manifest),'ZIP_payload_failures':zipbad,'ZIP_CRC_error':zipcrc,'new_source_files':len(sourcefiles),'all_source_byte_identical_to_parent':all(sha(old/n)==h for n,h in sourcemap.items()),'source_manifest':'SOURCE_MANIFEST.json','functional_code_sha256':sha(ROOT/'functional_smoke.py'),'run_plan_sha256':sha(ROOT/'RUN_PLAN.json'),'contract_sha256':contract(),'checkpoints_use_current_contract':all(r['metadata']['contract_sha256']==contract() for r in checkpointrows),'old_READINESS_byte_unchanged':sha(ROOT/'READINESS.json')==sha(old/'READINESS.json'),'formal_train_entry_byte_unchanged':sha(ROOT/'train.py')==sha(old/'train.py'),'formal_gate_closed':gateclosed,'no_B_H150_or_plant_safety_task_change':True,'owned_processes_exited':not alive,'no_Git_repository_present':not (ROOT.parent/'.git').exists(),'Git_mutations_performed':False,'environment_reinstalled':False,'shared_interpreter':str(original/'.venv/bin/python'),'package_integrity_not_scientific_promotion':True,'qualification':qualification}
put(ROOT/'PACKAGE_VERIFICATION.json',verification)
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
put(ROOT/'STATE.json',{'status':'STOPPED_QUALIFICATION_BLOCKED','phase':'COMPLETE_BOUNDED_STUDY','finished_client_time':now,'no_more_physics':True,'formal_Pilot_allowed':False,'next':'Recover full original matched authority and close legal-state reachability audit; no automatic next study'})
put(ROOT/'STOP.json',{'status':'STOPPED_QUALIFICATION_BLOCKED','unix':time.time(),'owned_processes_exited':True,'no_formal_Pilot_started':True,'no_automatic_next_package':True,'hard_4h_limit_respected':time.time()<plan['hard_stop_unix']})
# Human-readable results with exact scopes and evidence links.
summary='\n'.join(f'| {k} | {v} |' for k,v in qualification.items())
(ROOT/'PPO_FUNCTIONAL_SMOKE.md').write_text(f'''# PPO 功能测试

PPO_UPDATE_SMOKE_PASS=PASS；CHECKPOINT_RESUME_PASS=PASS。类别全程 UNQUALIFIED_TRAINING_SMOKE。不是正式训练，也不是RL学习成功。

随机初始化CPU MLP，actor/value各[16,16]，seed20261021，单环境，gamma=1，n_steps=8、batch=4、epoch=1。原robot–cuff–Human MuJoCo、证书/准入/governor/真实native执行链完整保留，无B/H150教师或模仿权重。

初始进程PID{initial['pid']}用8个真实transition完成1个PPO训练epoch、2次Adam step；保存checkpoint并退出。新进程PID{resume['pid']}核对policy、完整Adam tensors/超参数、Python/NumPy/Torch RNG、num_timesteps、n_updates、total_timesteps、progress_remaining和episode_num，8项完全一致；再用8个真实transition执行第2个epoch，Adam step计数2→4，权重再次变化。第三进程PID{evaluation['pid']}载入最终checkpoint且policy/optimizer冻结，执行完整有界任务评价。

总计2次PPO train调用、4次实际optimizer梯度更新。梯度裁剪后L2约0.5，全部有限非零，每次权重改变。不能把SB3 n_updates=2或13个parameter tensor的Adam step总和52误称为真实optimizer调用次数。checkpoint内部历史命名 `gradient_optimizer_steps_total` 是逐parameter step之和26/52，正确全局次数见 PPO_UPDATE_RESULTS.json。

两个训练rollout各8 decisions后，分别额外19个动作完成当前episode供raw审计；这38个tail动作没有进入optimizer。共16训练decisions +38审计tail +24冻结评价 =78真实RL决策；native physics343520步（含commissioning），其中TASK222920步，3个完整或失败终态episode。

恢复采用已声明的fresh physical episode：不恢复MuJoCo中途状态/partial rollout。policy、optimizer、RNG和SB3训练计数精确恢复；checkpoint `episodes_completed` 是本进程完整物理episode数1，累计数沿不可变parent链为2，另评价1个。SB3 episode_num为0是因为训练收集的8步没有包含终态，后续终态发生在审计tail；不伪造这个计数。

|进程|TASK s|结果|完整reward分项(progress,completion,force,variation)|
|---|---:|---|---|
'''+ '\n'.join(f'|{n}|{m["task_s"]:.3f}|{m["status"]}|{list(m["reward_totals"].values())}|' for n,m in zip(names,metrics))+f'''

冻结评价0/1成功，16.610s原planner拒绝将进入shank-table geometry的候选并ABORTED；这表示保护拒绝了该提议，不是实际Human发生穿透。PPO_TASK_SUCCESS=FAIL、PPO_FULL_QUALIFIED=FAIL。首个训练episode19.280s完成时policy中途更新，不作为冻结策略评价成功。

3/3新episode独立force/moment/phase积分、reward、终止、真实Human运动、certificate、immutable source、receipt/native torque ownership和executor退出全部PASS。恢复失败episode总progress仅1.78e-15浮点误差，completion=-10，无成功奖励。

两代checkpoint模型SHA256：
- 初代 `{checkpointrows[0]['model_sha256']}`
- 恢复更新后 `{checkpointrows[1]['model_sha256']}`

各zip/RNG/metadata SHA与逐字段恢复核对见 CHECKPOINT_RESUME_AUDIT.json。训练loss见 PPO_UPDATE_RESULTS.json，所有原始RESULT/START/END/日志保留在runs/。

物理子进程合计{wall:.3f}s，含guard启动合计{update['outer_guard_wall_seconds']:.3f}s；用户CPU {update['cpu_user_s']:.3f}s、system CPU {update['cpu_system_s']:.3f}s。单进程峰值RSS {update['peak_single_process_rss_KiB']/1024:.1f}MiB，最低可用RAM {update['minimum_available_RAM_GiB']:.3f}GiB，高于6GiB。guard将进程限制在单CPU affinity、单线程，无并行扩展。

当前实际端到端78/{wall:.3f}≈{rls/wall:.3f} decisions/s，约{nds/wall:.0f} native steps/s或{nds*.00025/wall:.3f}仿真秒/墙钟秒。此数字包含commissioning、tail和日志；16个优化器训练样本/两个完整审计episode的总wall是功能测试效率，不是长期训练吞吐估计。3个episode平均{wall/3:.1f}s。资源足够最小工程测试，尚无长期稳定性/多环境扩展证据。
''')
(ROOT/'NEXT_RESEARCH_DECISION.md').write_text('''# 下一研究决策

当前正式PPO Pilot禁止启动，预算0 episode /0 seed /0训练时间。本研究已STOP；不自动创建下一包或执行后续训练。

唯一推荐下一步：开展一次限定的“原匹配合同与合法失败可达性闭合审计”。先取回正式B/H150原匹配Master Contract及对应任务/安全/运动/因果资格矩阵，明确其模式身份与已部署native-event RL-B是否可比较；保留20.165s对冻结19.030回归的FAIL，按真正冻结要求识别最小执行修复并为任何动作/调度/接口变更登记新版本、重新做受影响物理回归。同期对自然phase/TASK timeout、HOLD不成立、绝对安全触发三类缺口给出合法可达证据或可独立审查的不可达论证。原严格G4要求保持，不自行用TEST_ONLY覆盖替换。

最少剩余阻碍：G4自然失败矩阵未闭合；冻结匹配执行回归失败且正式B/H150充分合同未部署；冻结PPO评价0/1成功，不能授予策略任务成功/全资格。optimizer更新和跨进程恢复的功能缺口本轮已经消除。

只有原严格训练启动门全部通过并完成对应策略/执行审查后，才能另行决定正式Pilot预算。当前不提供可直接执行的长训练命令，不自动扩大smoke。
''')
(ROOT/'REPORT.md').write_text(f'''# iHEAR Lab — RL-B G4 Closure & PPO Functional Readiness v1

本轮工程测试完成并STOP。PPO真实更新与跨进程恢复PASS；G4严格资格及冻结匹配评价仍FAIL，正式PPO Pilot不允许启动。报告时间{now}（Asia/Shanghai）。预计2–3小时是上限内建议，本轮证据足够后提前停止，未扩展实验。

|独立资格|结果|
|---|---|
{summary}

1. **runtime COMPLETE与19.030s匹配资格**：前者要求原task状态机完整phase、有效HOLD和causal native RETURN commit，phase10s/TASK30s；后者还要求冻结匹配的task/safety/motion/causal资格，部署的必要回归是19.030±0.050s。二者独立，详见 TASK_QUALIFICATION_CONTRACT.md。配置原dwell0.5s、既有wrapper HOLD timing floor1s和观测HOLD1.020s分别保留，不混为一种合同。
2. **20.165s随机任务**：RUNTIME_TASK_COMPLETE=PASS，MATCHED_19_03_QUALIFIED=FAIL。9.260+1.020+9.885s均符合原runtime期限，总时长超出匹配窗口1.135s。原ZIP/部署包未包含正式B/H150完整历史匹配Master Contract，不能自行补写其充分条件；该部分审查NOT_EVALUABLE不掩盖已知时长FAIL。
3. **G4真实物理通过**：原正常完成、零进度/停滞拒绝、连续两次planner FAILED、planner失败、合法fallback、自然partial reward、terminated/truncated与真实双episode reset独立性。原9个episode本轮只读raw/phase力积分重新核对9/9通过；3个新PPO episode完整独立raw reward、force、实际Human motion和receipt ownership也通过。
4. **只有TEST_ONLY及缺失项**：phase/TASK timeout、HOLD不成立、绝对安全触发的自然证据仍NOT_EVALUABLE；原注入/单元链PASS，本轮41项协议/接口测试全部PASS。20次连续拒绝压力只有TEST_ONLY；自然观察只证明已有两次FAILED及其后原NO_FEASIBLE路径，绝不声称任意次数压力覆盖。详见 G4_STRICT_VALIDATION.md、G4_TEST_COVERAGE.json。
5. **G4是否闭合**：否，G4_STRICT_PASS=FAIL。保留原严格自然失败矩阵门，G4_TEST_HARNESS_COVERAGE=PASS不改变它。未绕过保护制造自然违规，也未把有限未观察证明成全状态不可达。
6. **PPO真实更新**：是。随机初始化CPU小网络，1seed、单环境、16个真实训练transition，2次PPO train/epoch、4次实际Adam梯度步；全部有限非零且权重改变。另38个完成episode的审计tail不进入优化器。无B/H150教师轨迹/模仿权重。
7. **跨进程恢复**：是。初始PID{initial['pid']}保存后退出；PID{resume['pid']}核对权重、完整Adam、三类RNG和8个训练状态字段后，从8→16训练steps、Adam2→4继续真实rollout和更新；第三PID{evaluation['pid']}再次载入并冻结评价。恢复是fresh physical episode，不声称MuJoCo中途连续恢复。SHA、计数语义与全部核对见 CHECKPOINT_RESUME_AUDIT.json。
8. **资源/吞吐**：3个新episode、78真实decisions、343520 native steps（TASK222920）；物理子进程总{wall:.1f}s，约{rls/wall:.3f}decisions/s，平均{wall/3:.1f}s/episode。最低可用RAM{update['minimum_available_RAM_GiB']:.2f}GiB、单进程峰值RSS约{update['peak_single_process_rss_KiB']/1024:.0f}MiB；无OOM、资源超时或MuJoCo warning。单CPU affinity/单线程的工程预算足够，长期正式吞吐尚未验证。
9. **允许正式Pilot吗**：不允许。READINESS与train.py门禁逐字节保留，未写入新的正式PASS。PPO_UPDATE_SMOKE_PASS与CHECKPOINT_RESUME_PASS不授予G4或正式训练资格。
10. **当前Pilot episode/seed/时间预算**：0/0/0。没有开始正式训练。不会自动按million decisions扩大规模，也不会自动启动下一研究包。
11. **最少还缺什么**：自然timeout/HOLD失败/绝对安全触发三类严格G4证据或正式可达性审查闭合；原匹配合同来源和冻结执行回归闭合。冻结策略评价16.610s因原shank-table几何筛查拒绝candidate而ABORTED，0/1成功，PPO_TASK_SUCCESS和PPO_FULL_QUALIFIED均FAIL。首个训练episode成功不等于冻结策略学会任务。

本轮新物理仅3个episode，远低于12上限。所有物理进程3 START/3 END、episode3 START/3 END闭合，owned PID和native owner/executor均退出。保留原始失败、日志、transitions、native journal及两代checkpoint；计数/时钟记录的已知命名限制公开写入 ATTEMPT_ACCOUNTING.json 与 PPO_UPDATE_RESULTS.json，未冒充科学资格。

原ZIP、原部署与旧修复包共{len(protected)}文件hash保护通过；源文件{len(sourcefiles)}份与上一隔离版本逐字节相同，原ZIP450个manifest载荷再校验通过。未改正式B/H150、Human/robot/cuff物理、安全限制、目标、HOLD或deadline，未更改action/scheduler/execution接口；只新增独立smoke入口、审计记录和报告，未重装环境。观察到的EXECUTION_PARITY_PASS是核心物理执行对照与新raw审计范围，完整冻结execution gate仍FAIL，host realtime NOT_EVALUABLE。

目录无Git checkout，branch/HEAD不可用；无stage/commit/push/merge/reset/stash/clean。全部新文件位于本隔离研究包，源码/输出manifest、保护hash与封存结果见 PACKAGE_VERIFICATION.json、SOURCE_MANIFEST.json、OUTPUT_MANIFEST.json。最终状态 STOPPED_QUALIFICATION_BLOCKED。唯一下一步见 NEXT_RESEARCH_DECISION.md。
''')
(ROOT/'README.md').write_text('# 研究包入口\n\n请先读 REPORT.md。该包仅 UNQUALIFIED_TRAINING_SMOKE；正式Pilot禁止。状态 STOPPED_QUALIFICATION_BLOCKED。\n\n完整合同、G4矩阵、PPO更新/恢复、原始runs、manifest和下一决策均在本目录。功能测试已执行，不要把示例/历史入口当作授权重启。\n')
outputs={str(p.relative_to(ROOT)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in ROOT.rglob('*') if p.is_file() and p.name!='OUTPUT_MANIFEST.json' and '__pycache__' not in p.parts}
put(ROOT/'OUTPUT_MANIFEST.json',{'files':outputs,'self_excluded':True,'status':'SEALED','created_unix':time.time()})
print(json.dumps({'status':'STOPPED_QUALIFICATION_BLOCKED','qualification':qualification,'integrity':verification['status'],'files':len(outputs),'wall_s':wall,'new_episodes':3,'optimizer_steps':len(steps),'owned_pids_alive':alive},ensure_ascii=False))
