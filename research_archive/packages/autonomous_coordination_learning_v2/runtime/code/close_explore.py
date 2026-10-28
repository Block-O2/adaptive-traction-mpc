from explore_common import *
import subprocess,collections,shutil,datetime,importlib.util
WIN=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1')
def git_state(root,scoped=False):
 def call(*args):
  r=subprocess.run(['git','-C',str(root),*args],capture_output=True,env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'),timeout=180);return dict(returncode=r.returncode,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace'))
 def args(*a):return a+('--','Desktop/Coding/adaptive_traction_mpc') if scoped else a
 idx=call('rev-parse','--git-path','index')['stdout'].strip();p=Path(idx);p=p if p.is_absolute() else root/p
 return dict(branch=call('branch','--show-current'),head=call('rev-parse','HEAD'),status=call(*args('status','--porcelain=v1','--untracked-files=all')),diff=call(*args('diff','--binary')),staged=call('diff','--cached','--binary'),index_sha256=sha(p) if p.is_file() else None,scoped=scoped)
def main():
 assert (S/'CAMPAIGN_STOP.json').exists(),'JOIN_CAMPAIGN_BEFORE_CLOSEOUT'
 protocol=load(S/'EXPERIMENT_PROTOCOL.json');motion=load(S/'MOTION_ACCEPTANCE_PROTOCOL.json');events=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends=[r for r in events if r['event']=='END'];measured=[load(p) for p in sorted((S/'reports').glob('*_MEASURED.json'))];by={r['id']:r for r in measured};block=load(S/'BLOCKER.json') if (S/'BLOCKER.json').exists() else None
 if not (S/'SEARCH_RESULTS.json').exists():save(S/'SEARCH_RESULTS.json',dict(status='BLOCKED_BEFORE_DISCOVERY_RESULTS',comparisons=[],measured_ids=list(by),attempts=events))
 search=load(S/'SEARCH_RESULTS.json');search['attempts']=events;search['not_run']=[p.stem for p in sorted((S/'queue').glob('*.json')) if p.stem not in {r['id'] for r in starts}];search['all_registered_config_ids']=[p.stem for p in sorted((S/'queue').glob('*.json'))];search['denominators']=dict(attempts=len(starts),measured_full_tasks=len(measured),discovery_candidate_pool=12,discovery_table_attempts=sum(r['config'].get('split')=='search' and r['config'].get('id') not in ['001_search_B','002_search_frozen_M2'] for r in starts));save(S/'SEARCH_RESULTS.json',search)
 val=load(S/'VALIDATION_RESULTS.json');historical=load(S/'HISTORICAL_MOTION_FAILURE_AUDIT.json');lineage=[]
 for r in starts:
  ident=r['id'];f=S/'reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');lineage.append(dict(id=ident,config=r['config'],input_sha256=sha(S/'queue'/(ident+'.json')),code_manifest_sha256=r['code_manifest_sha256'],execution=load(f) if f.exists() else None,status='MEASURED' if ident in by else 'FAILED_OR_UNREVIEWED',partial_compute=load(S/'output'/(ident+'_PARTIAL_COMPUTE.json')) if (S/'output'/(ident+'_PARTIAL_COMPUTE.json')).exists() else None))
 sampled_checks=[]
 for run in lineage:
  if not run['execution']:continue
  for r in run['execution']['rows']:
   sel=r.get('selection')
   if not sel:continue
   start=sel['context']['start_m'];knots=np.r_[start,start+(1-start)*np.array([.1,.4,.7]),1.];values=np.r_[0.,np.array(r['applied_current_K3'])*.2,0.]
   for m in r['native_coordination_metadata']:
    if m.get('status')=='ACCEPTED':
     expected=float(np.interp(m['nominal_common'],knots,values));sampled_checks.append(dict(id=run['id'],request_id=r['request_id'],native_delta=m['delta'],expected_from_applied_K3=expected,error=abs(expected-m['delta']),actual_native_steps=r['actual_native_steps'],physically_executed_nonzero=r['physically_executed_nonzero']))
 save(S/'CANDIDATE_EXECUTION_LINEAGE.json',dict(attempts=lineage,not_run=search['not_run'],sampled_K3_consistency=sampled_checks,max_sampled_K3_error=max([r['error'] for r in sampled_checks] or [0]),source='actual source-stamped TASK proposal/certification/lifecycle/half-open native segment/command receipts',proposed_is_not_executed=True,inherited_field_semantics='new_selected_Q_executed is an inherited receipt-join field; for registered_table arms it means a new table selection executed, NOT a Q-selected action. Q_calls=0 on all table arms; only frozen M2 baseline uses Q.'))
 ep=WIN.parent/'single_human_expert_e_v1';efiles=[ep/'bounded_search.py',ep/'search_isolated_resume.py',ep/'coordination_adapter.py',ep/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',ep/'output/E_SEARCH_BEST_KNOWN.json',ep/'output/SINGLE_HUMAN_EXPERT_E_V1_REPORT.md']
 save(S/'HISTORICAL_E_REFERENCE_AUDIT.json',dict(read_only=True,sources={str(p):sha(p) for p in efiles if p.is_file()},reference=load(ep/'output/E_SEARCH_BEST_KNOWN.json'),reuse='Native phase/issued-slot lookup and full-task evaluation contract reused conceptually; high-budget CEM not dispatched under24 total attempts. Original E raw numeric result is not a matched current comparator.',physics_added=0))
 save(S/'MOTION_FORCE_TRADEOFFS.json',dict(measured=measured,discovery_comparisons=search.get('comparisons',[]),validation=val,historical_failure_counts={k:v['counts'] for k,v in historical['profiles'].items()},motion_protocol_sha256=sha(S/'MOTION_ACCEPTANCE_PROTOCOL.json'),population_scope='same exposed simulated nominal Human, finite task seeds, cold commissioning; not clinical'))
 optional='''# Optional single-freedom extension decision

Stage D new physical attempts: 0. NOT_NATIVE_EXECUTABLE applies to any independently controlled common-progress offset suggested conceptually here; none was implemented or simulated.

The existing v2 graph already accepts arbitrary finite spatial PWL knots. Temporal smoothing cannot be assumed from such knots because only the native nominal target is sampled and the scheduler owns the physical profile. The bounded C slice does not exhaust knot timing, action amplitude or issued-slot combinations, so no evidence justifies adding a new control dimension in this package.

If a later audit establishes a need for independent common-progress control, the minimal conceptual change would be one bounded scalar added to both normalized joint target progresses, followed by original native target/schedule evaluation and current-state admission. It would change common task progress and could change timing/dose, force/moment peaks, terminal ownership and safe fallback proofs. It therefore requires a separately versioned contract and requalification. There is no demonstration that it resolves the force/knee-motion conflict. This is a contract-risk description, not a discovered physical solution, executable B action or host-clock benefit.
'''
 (S/'OPTIONAL_SPACE_EXTENSION.md').write_text(optional)
 passed=val.get('status')=='VALIDATED_B_RELATIVE_RESEARCH';recommend='A' if passed else 'E';terminal=val.get('status') if not block else 'STOPPED_AT_NATIVE_COMPARISON_GATE'
 if '001_search_B' in by:
  import matplotlib
  matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
  for c in search.get('comparisons',[]):
   color='#147d64' if c['acceptance_pass'] else '#b74343';label=c['candidate'].split('_')[0]
   for ax,key in zip(axes,['velocity_deg_s/p95_abs','acceleration_deg_s2/p95_abs']):
    ax.scatter(c['gain_percent'],c['burden_ratios'][key][1],color=color,s=48)
    if c['acceptance_pass'] or label=='002':ax.annotate(label,(c['gain_percent'],c['burden_ratios'][key][1]),xytext=(5,8),textcoords='offset points',fontsize=9)
  for ax,title in zip(axes,['Knee p95 speed / B','Knee p95 acceleration / B']):
   ax.axhline(1,color='#777777',ls=':');ax.axhline(1.1,color='#d39823',ls='--');ax.set(xlabel='Full-task J_F reduction versus B (%)',ylabel=title,title=title);ax.grid(alpha=.18)
  fig.suptitle('Discovery only: green = primary gates pass; red = excluded\nLabels identify eligible tables and frozen M2; selected table failed held-seed validation',fontsize=11)
  fig.savefig(S/'COORDINATION_TRADEOFF.png',dpi=160);fig.savefig(S/'COORDINATION_TRADEOFF.svg');plt.close(fig)
 mod=historical['profiles']['moderate']['counts'];strict=historical['profiles']['strict']['counts'];wide=historical['profiles']['wide']['counts']
 table='| attempt | J_F N·s | physical / causal | nonzero native plans | acceptance versus B |\n| --- | ---: | --- | ---: | --- |\n'
 comps={c['candidate']:c for c in search.get('comparisons',[])}
 for pair in val.get('pairs',[]):
  for k in ['candidate','M2']:
   if k in pair:comps[pair[k]['candidate']]=pair[k]
 for r in starts:
  ident=r['id'];a=by.get(ident);c=comps.get(ident)
  if a:table+=f"| {ident} | {a['J_F_N_s']:.6f} | {a['axes']['PHYSICAL_TASK_VALID']} / {a['axes']['HOST_EXECUTION_CAUSAL_VALID']} | {a['axes']['nonzero_execution_count']} | {'PASS' if c and c['acceptance_pass'] else ', '.join(c['failed_requirements']) if c else 'baseline'} |\n"
  else:table+=f'| {ident} | NOT_EVALUABLE | failed/unreviewed | NOT_EVALUABLE | NOT_EVALUABLE |\n'
 decisions=[
 '现有接口表达相位内、空间进度上的反对称目标分配；raw v2支持任意有限PWL图，K3前端固定三个剩余进度结点、每phase最多五个issued slots；不直接控制物理时长、速度或加速度。',
 '旧ordinary候选库覆盖稀疏，存在尚未搜索的合法连续幅度/阶段/slot/结点组合。是否遗漏有价值方案，只能由本轮实际结果限定回答：'+('发现并经两个保留seed验证了B-relative候选。' if passed else '本轮未取得可独立验证的成功证据，不能断言不存在。'),
 '降低J_F的结果见逐attempt和同seed比较；'+('候选相对B达到注册收益条件。与旧M2的J_F差及平顺性代价分别报告，不能称全面支配。' if passed else '没有足够证据证明比旧M2更合理的可执行协调策略。'),
 '真实knee/hip密集q/dq及导数决定运动结论；'+('保留seed通过注册10%非劣、剂量和补偿界。' if passed else '独立运动非劣验证未成立。')+' jerk原始及SG5/21敏感性保留，均非临床阈值。',
 f'原moderate筛查67非零行：速度{mod.get("velocity",0)}、加速度{mod.get("acceleration",0)}、剂量{mod.get("dose",0)}、phase-shape{mod.get("phase_shape",0)}、多类{mod.get("multiple_categories",0)}；可选jerk失败{mod.get("jerk_optional_failure",0)}。Phase-shape使所有非零被完整profile排除，但其余条件也造成大量失败。',
 '反对称归一化目标分配具有真实结构边界；但当前有限候选搜索失败不能证明这些边界是主要性能瓶颈。原生接口比固定K3库更广，需区分候选覆盖和接口表达。',
 '没有引入或运行新自由度；Stage D不具备足够必要性证据，NOT_RUN，不宣称新空间有较好物理解。',
 '合法执行只按native接受、lifecycle ACTIVATED、实际command receipts及对应native steps确认。Proposal、局部feasible或选择日志均不单独证明执行。'+('本轮完整合法执行证据见lineage。' if measured else '本轮合法完整比较尚未建立。'),
 '候选覆盖、表达、执行和物理权衡分别保留；'+('该有限验证支持优先改善原接口搜索与数据，但不消除其他瓶颈。' if passed else '当前证据不足以唯一归因，尤其不能将研究motion失败变成人体不安全结论。'),
 '本轮没有Q训练。'+('优先建立合法受约束参数搜索/生成数据；固定候选排序的收益空间仍有限，不能仅扩大Q网络。' if passed else 'ordinary历史池fixed regret=0与稀疏候选覆盖不支持仅扩大同一库的评分网络；受约束参数生成是可研究的覆盖方向，但没有被本轮验证为成功。先解决比较与收益可重复性，再决定训练目标。')]
 head=(f'# iHEAR Lab — Executable Coordination Space Exploration v1\n\n终态：**{terminal}**。唯一主要方向：**{recommend}. '+('原接口已有可验证B-relative方案，改善搜索与训练数据。' if passed else '证据不足，完成特定下一项诊断。')+'**\n\n')
 summary=f'实际新增物理attempt **{len(starts)}/24**（包括失败/无效），完整密集测量 **{len(measured)}**，搜索候选总数 **12**；全部串行，没有内部完整任务rollout、Q/Neural Q训练或persistent Human session。'+(f' 阻断证据：`{block["id"]}`：`{block["error"]}`。相关实验立即停止，未重试或修改原生合同。' if block else '')+'\n\n'
 report=head+summary+table+'\n## 历史失败与预注册评价\n\n'+f'80条历史行来自13snapshot/4source groups；其中13zero、67nonzero，74ordinary+6历史G-head。严格层速度/加速度/剂量/phase-shape失败数为{strict.get("velocity",0)}/{strict.get("acceleration",0)}/{strict.get("dose",0)}/67；moderate为{mod.get("velocity",0)}/{mod.get("acceleration",0)}/{mod.get("dose",0)}/67；wide为{wide.get("velocity",0)}/{wide.get("acceleration",0)}/{wide.get("dose",0)}/67。分类重叠，不相加作为分母。逐行失败及组合已导出，历史PASS/FAIL不改。\n\n'
 report+='新协议在首attempt前冻结：保留原native安全、force/moment absolute peak、ROM、clearance、任务目标/终点、scheduler/governor、40ms bridge、100ms expiry、current-state admission、ownership及fallback。新增10% raw speed/acceleration/jerk非劣条件（knee/hip），excursion绝对差≤0.5°、累计角位移±5%、端点/phase boundary≤0.5°、整体及各phase时长差≤0.1s；bounded moment integral≤25%、tracking RMS增量≤0.5°、峰值补偿≤5%，同时必须原安全PASS。Phase-shape单独诊断；没有将原历史失败改成新PASS。缺乏绝对临床界，故采用历史moderate比较档并报告0/5/10/25%敏感性；新结果后未变阈值。\n\n'
 report+='## 搜索与验证的科学层级\n\n12个固定注册K3候选覆盖RETURN historical design缩放0.025/0.05/0.1/0.2/0.35/0.5、双phase缩放0.05/0.2，以及RETURN flat/early/late/tent。原始B zero及冻结M2在相同host协议和nominal seed下运行。搜索用实际完整物理任务，不优化旧Q分数；旧Q只作为未更新基线。历史E的1360.602793 N·s仅作不同科学时钟/commissioning参考，未相减。未穷尽30D空间，不能将有限负结果升级为空间无解。\n\n保留seed2026100902/2026100903只在搜索选择冻结后运行；'+('已完成两个三臂比较，结果见VALIDATION_RESULTS.json。' if len(val.get('pairs',[]))==2 else '独立验证未完成，不能称VALIDATED。')+' 这是完整初始条件比较，不是同中间state counterfactual。各次commissioning模型/初态差异保留；未强行共享不可恢复完整state，也未宣称V_commit=host V_replan。\n\n'
 report+='## 最终十问\n\n'+'\n\n'.join(f'{i}. {s}' for i,s in enumerate(decisions,1))+'\n\n'
 nextdiag='在现有合法原生执行链上，完成一组固定nominal初始条件的B zero与注册低幅RETURN table完整任务比较，先确认完整physical/causal/trace门限。' if block else '建立并验证包含commissioning、完整native初态、scheduler/lifecycle与RNG的合法初始状态恢复门限，再对本轮冻结候选与B做匹配完整任务比较；不得拼接近似状态或绕过admission。目标是分离冷启动波动与residual作用，原运动接受协议保持不变。'
 report+='唯一下一方向：'+('A，扩大已验证原接口候选搜索与可追溯参数数据。' if passed else 'E，'+nextdiag)+' 本轮STOP，不开始训练、接口合并或下一包。\n\n'
 report+='## 执行与保护\n\n指定Python -B依次执行bootstrap.py、preflight_explore.py、campaign_explore.py（内部run_one/review_attempt）、close_explore.py。新增harness只在独立side-study中，host_adapter唯一功能增加是选择registered table coordinator；原B源码仅路径迁移，调度/准入/安全合同无功能改动。Native certificates仍通过原准备及激活路径。Git stage/commit/push/reset/stash/branch切换0；全球RAM/swap/电源/调度改变0，未终止无关进程。曾中断本包只读Git清单，因为Windows目录无自身.git且解析到用户根目录；该失败保留，之后Windows状态限定工作区路径。正式主Git保护与8363文件hash核验见PACKAGE_VERIFICATION.json。\n\n原R2、strict55逐run独立保留，observed FAST不是正式实时资格。本轮无硬件测试。最终报告、原始trace、失败log、候选mask/实际native execution、派生motion和完整任务积分均保留。\n'
 if (S/'COORDINATION_TRADEOFF.png').exists():report+='\n![Registered discovery force–motion tradeoff](COORDINATION_TRADEOFF.png)\n'
 if val.get('pairs'):
  report+='\n## 保留seed逐对结果\n\n| seed | candidate gain vs B | acceptance | knee p95 speed / B | knee p95 acceleration / B | candidate J_F − M2 N·s |\n| --- | ---: | --- | ---: | ---: | ---: |\n'
  for pair in val['pairs']:
   c=pair['candidate'];report+=f"| {pair['seed']} | {c['gain_percent']:.4f}% | {'PASS' if c['acceptance_pass'] else ', '.join(c['failed_requirements'])} | {c['burden_ratios']['velocity_deg_s/p95_abs'][1]:.4f} | {c['burden_ratios']['acceleration_deg_s2/p95_abs'][1]:.4f} | {pair['candidate_minus_M2_J_F_N_s']:.6f} |\n"
 if (S/'COLD_START_ATTRIBUTION_LIMITS.json').exists():
  ctx=load(S/'COLD_START_ATTRIBUTION_LIMITS.json');selected=load(S/'CANDIDATE_SELECTION.json').get('selected') if (S/'CANDIDATE_SELECTION.json').exists() else None
  if selected:
   ar=next((r for r in ctx['discovery'] if r['id']==selected['candidate']),None)
   if ar:
    report+=f"\n发现候选{selected['candidate']}相对B的J_F下降{selected['gain_N_s']:.6f} N·s；各phase delta为{ar['phase_delta_J_F_N_s']}。RETURN-only方案的OUTBOUND差不能归因于尚未发生的残差；commissioning参数最大绝对差为{ar['commissioning_max_abs_differences']}，真实TASK入口q/dq差亦导出。该混杂限制不能被完整任务PASS消除。\n"
 if (S/'BASELINE_REPEAT_RESULTS.json').exists():
  br=load(S/'BASELINE_REPEAT_RESULTS.json');report+=f"\n同discovery seed的三次B-zero冷启动J_F为{[r['J_F_N_s'] for r in br['rows']]} N·s，range={br['J_F_range_N_s']:.6f} N·s，phase ranges={br['phase_J_F_range_N_s']}。这两次新增对照在运行前单独注册，使用剩余预算；由已暴露发现结果触发，属于归因诊断，未重选候选、未修改容差或改用最好B作为比较基线。n=3描述性范围不是误差界或统计显著性。\n"
 report+='\n配置中的performance_context沿用旧描述性字符串；本轮新runner没有旧45s资源采样器，不能将该字符串作为资源采样证据。仅保留实际read-only资源观测，不进行资源资格推断。\n'
 (S/'REPORT.md').write_text(report)
 # Mechanical checks independent of candidate choice; no more physical execution.
 protected=load(S/'preservation/HISTORY_BEFORE.json');changed=[]
 for p,h in protected.items():
  if not Path(p).is_file() or sha(p)!=h:changed.append(p)
 before=load(S/'preservation/GIT_BEFORE.json');gchecks=[];after={}
 for name,b in before.items():
  iswin=name.startswith('/mnt/c/');root=Path('/mnt/c/Users/HankL') if iswin else Path(name);a=git_state(root,scoped=iswin);after[name]=a
  keys=['branch','head','index_sha256','staged']+([] if iswin else ['status','diff']);gchecks.append(dict(root=name,checked_keys=keys,unchanged=all(a[k]==b[k] for k in keys),scope='Windows user-root Git branch/HEAD/index/staged preserved; initial unscoped status interrupted, final status/diff restricted to research path' if iswin else 'full primary repository state'))
 save(S/'preservation/GIT_AFTER.json',after)
 code=load(S/'CODE_MANIFEST.json');code_changed=[p for p,h in code.items() if not (S/p).is_file() or sha(S/p)!=h]
 gzchecks=[]
 for r in starts:
  f=S/'source/results'/r['id']/'runtime_artifacts.json.gz'
  if f.exists():
   h=hashlib.sha256();n=0
   with gzip.open(f,'rb') as src:
    for chunk in iter(lambda:src.read(2**20),b''):h.update(chunk);n+=len(chunk)
   gzchecks.append(dict(id=r['id'],CRC_EOF_PASS=True,uncompressed_bytes=n,uncompressed_sha256=h.hexdigest(),compressed_sha256=sha(f)))
 procs=[]
 for p in Path('/proc').iterdir():
  if p.name.isdigit() and int(p.name)!=os.getpid():
   try:
    cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
    env=(p/'environ').read_bytes().decode(errors='replace')
    owned=str(S/'code/campaign_explore.py') in cmd or str(S/'code/run_one.py') in cmd or str(S/'code/baseline_diagnostic.py') in cmd or ('FAST_M2_CONFIG='+str(S)) in env
    if owned:procs.append(dict(pid=int(p.name),cmd=cmd,ownership='exact study worker command or FAST_M2_CONFIG environment'))
   except OSError:pass
 required=['REPORT.md','EXPERIMENT_PROTOCOL.json','COORDINATION_SPACE_AUDIT.md','MOTION_ACCEPTANCE_PROTOCOL.md','MOTION_ACCEPTANCE_PROTOCOL.json','SEARCH_RESULTS.json','CANDIDATE_EXECUTION_LINEAGE.json','MOTION_FORCE_TRADEOFFS.json','OPTIONAL_SPACE_EXTENSION.md','VALIDATION_RESULTS.json']
 history_added=[]
 for name in ['b_fast_jitter_m2_host_v1','m2_host_generalization_attribution_v1','m2_neural_q_motion_v1','m2_motion_counterfactual_ranking_v1']:
  history_added.extend(str(p) for p in (S.parent/name).rglob('*') if p.is_file() and str(p) not in protected)
 source_changed=[];old=S.parent/'m2_host_generalization_attribution_v1'
 for p in (S/'source/stages').rglob('*'):
  if not p.is_file():continue
  orig=old/p.relative_to(S)
  if not orig.is_file():source_changed.append(str(p));continue
  if p.suffix in ['.py','.json','.xml','.yaml','.yml','.toml','.sh']:
   expected=orig.read_text().replace(str(old),str(S)).replace('m2_host_generalization_attribution_v1','m2_comprehensive_coordination_search_v1')
   if p.read_text()!=expected:source_changed.append(str(p))
  elif sha(p)!=sha(orig):source_changed.append(str(p))
 checks=dict(required_files=all((S/n).is_file() for n in required),all_attempts_end={r['id'] for r in starts}=={r['id'] for r in ends},unique_attempt_ids=len(starts)==len({r['id'] for r in starts}),attempt_cap=len(starts)<=24,wall_cap=time.time()<=protocol['deadline_unix'],history_unchanged=not changed,history_file_sets_unchanged=not history_added,git_unchanged=all(r['unchanged'] for r in gchecks),registered_code_unchanged=not code_changed,native_source_path_only=not source_changed,task_owned_workers_exited=not procs,gzip_integrity=all(r['CRC_EOF_PASS'] for r in gzchecks),phase_integral_closure=all(r['phase_cost']['status']=='COMPLETE_RAW_CLOSURE_PASS' for r in measured),sampled_K3_native_metadata_consistent=all(r['error']<1e-12 for r in sampled_checks))
 save(S/'PACKAGE_VERIFICATION.json',dict(status='PASS' if all(checks.values()) else 'FAIL',mechanical_only=True,scientific_terminal=terminal,checks=checks,history_files=len(protected),history_changed=changed,history_added=history_added,source_changed=source_changed,code_changed=code_changed,git=gchecks,workers_remaining=procs,actual_attempts=len(starts),full_tasks_measured=len(measured),gzip_checks=gzchecks,native_steps=sum(r['native_steps'] for r in measured),wall_elapsed_s=time.time()-protocol['start_unix'],protection_limits='Interrupted initial unscoped Windows status is NOT_EVALUABLE. Primary Linux Git full state and Windows root HEAD/index/staged checked; report folder additions expected. No formal scientific/realtime/clinical qualification implied.'))
 save(S/'PACKAGE_CLOSED.json',dict(unix=time.time(),elapsed_s=time.time()-protocol['start_unix'],actual_attempts=len(starts),STOP=True,no_auto_followup=True,worker_exit_verified=not procs))
 # Deliver a full review copy; preserve raw Linux authority and link in manifest.
 manifest={str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in S.rglob('*') if p.is_file() and p.name!='FULL_PACKAGE_MANIFEST.json'};save(S/'FULL_PACKAGE_MANIFEST.json',dict(canonical=str(S),files=manifest))
 shutil.copytree(S,WIN,dirs_exist_ok=True)
 mismatches=[p for p,v in manifest.items() if not (WIN/p).is_file() or sha(WIN/p)!=v['sha256']];save(WIN/'DELIVERY_VERIFICATION.json',dict(status='PASS' if not mismatches else 'FAIL',copied_files=len(manifest),mismatches=mismatches,canonical=str(S)))
 print(json.dumps(dict(status=terminal,checks=checks,attempts=len(starts),full_tasks=len(measured),recommendation=recommend,delivery_mismatches=len(mismatches),elapsed_s=time.time()-protocol['start_unix'])),flush=True)
if __name__=='__main__':main()
