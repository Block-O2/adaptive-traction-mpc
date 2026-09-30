"""Chinese Q15–19 report rendering from actual measured artifacts only."""
import argparse
import json
from pathlib import Path
from evidence_io import read_json
from latency_tools import distribution


def fmt(value):return '未测量' if value is None else f'{value:.3f}'
def stat_row(label,stats):
    return '| '+label+' | '+str(stats.get('count',0))+' | '+' | '.join(fmt(stats.get(k)) for k in ('median','p95','p99','maximum'))+' |'
def stat_table(rows,unit='ms'):
    return '\n'.join(['| 范围 | 样本数 | 中位数 | p95 | p99 | 最大值 |',
                      '|---|---:|---:|---:|---:|---:|',*[stat_row(label,stats) for label,stats in rows]])+f'\n\n单位：{unit}。'


def unique_updates(updates):
    unique={};pending=[];failed=[]
    for index,row in enumerate((updates or {}).get('repetition_boundary_updates',[])):
        if row.get('stage','').startswith('offline_'):continue
        if row.get('wall_s') is not None:
            key=(row.get('sha256'),row.get('path'))
            if key==(None,None):key=('unidentified_job',index)
            unique.setdefault(key,row)
        if row.get('stage')=='update_pending':pending.append(row)
        if 'failed' in row.get('stage','') or 'rejected' in row.get('stage',''):failed.append(row)
    return list(unique.values()),pending,failed


def render_section(profile,cpu,*,gate=None,updates=None,pilot=None,scaling=None,capture_profile=None):
    if not profile.get('source_artifacts') or not cpu.get('models'):
        raise ValueError('actual full host profile and actual CPU models required')
    full_rows=[('原始传感捕获 → 参考验证完成',profile['sample_capture_to_reference_validated_ms']),
               ('原始传感捕获 → 实际命令激活',profile['sample_capture_to_actual_activation_ms'])]
    exact=profile.get('exact_research_to_validation_activation_boundaries_ms',{})
    for key,label in [('adapter_start_to_reference_validated_ms','研究决策开始 → 参考验证完成'),
                      ('adapter_start_to_actual_activation_ms','研究决策开始 → 实际命令激活'),
                      ('first_feature_start_to_reference_validated_ms','首个特征开始 → 参考验证完成'),
                      ('first_feature_start_to_actual_activation_ms','首个特征开始 → 实际命令激活'),
                      ('reference_selected_to_actual_activation_ms','选定参考 → 实际命令激活')]:
        full_rows.append((label,exact.get(key,{})))
    text=['### 在线计算与更新（问题 15–19）',
          '以下是 Scientific Simulation 的实际主机剖析。模型属于固定 MATCHED pacing（1.3 倍注册段时长）和明确 continuation context；native 绝对目标补充研究未混入拟合。主机时间不会推进冻结的生产者仿真 epoch，因此这些数据不能认证硬件实时行为。',
          '**15．端到端高层决策延迟是多少？**',stat_table(full_rows),
          '传感捕获早于 observation ready，故捕获到验证/激活是比所需观察就绪边界更宽的实际测量；特征边界采用同源绝对单调时间戳，缺失时保留“未测量”。适用样本数见表，p99 是样本分位数而非最坏时间证明。']
    if profile.get('snapshot_capture_extra_io_source_count'):
        text.append('该剖析包含用于保存 immutable deployable snapshot 的额外文件 IO；它属于捕获专用运行，不能代替所选配置的正常模型执行验证。只有明确标记的捕获运行带此 IO 注记。')
    else:text.append('此剖析未标记 snapshot 捕获 IO；正常运行的安全/任务有效性及模型 SHA 仍须由相应 rollout provenance 独立确认。')
    if capture_profile:
        text+=['独立 capture 专用运行含 immutable snapshot 文件 IO，不能替代正常运行；配置也有差别，不能把两次运行的延迟差值解释为 IO 因果开销。该运行实际捕获 → 激活：',
               stat_table([('capture 专用运行，额外 IO',capture_profile['sample_capture_to_actual_activation_ms'])])]
    roles=profile.get('clean_role_timings_ms',{})
    text+=['观察到的角色延迟（排除明确标记的捕获 IO 运行）：',stat_table([
        ('首个 pattern 选择：捕获 → 激活',roles.get('first_pattern_selection',{}).get('capture_to_activation_ms',{})),
        ('已提交 continuation：捕获 → 激活',roles.get('continuation',{}).get('capture_to_activation_ms',{})),
        ('其中 moving handoff：捕获 → 激活',roles.get('moving_continuation',{}).get('capture_to_activation_ms',{}))]),
        '**16．哪部分主导延迟？**']
    component_rows=[]
    for key,label in [('legacy_planner_ms','原始 planner 比较候选'),('proposal_ms','研究 proposal 枚举'),('feasibility_scheduling_ms','研究候选调度/硬筛选'),
                      ('feature_ms','特征构建'),('inference_selection_ms','批量 Q 推断和选择')]:
        component_rows.append((label,profile.get('research_components_ms',{}).get(key,{})))
    for key,label in [('worker_to_main_scheduling_ms','worker 完成到主线程收集'),
                      ('validation_and_command_construction_ms','当前状态参考验证及命令构建')]:
        component_rows.append((label,profile.get('lifecycle_components_ms',{}).get(key,{})))
    text.append(stat_table(component_rows))
    text.append('adapter decision_total 的结束点是参考选择；它未覆盖 escape preparation、worker 主线程收集、当前状态参考验证和实际激活，不能称为端到端决策延迟。候选 feasibility/scheduling 的准入也不等于之后 activation validator 的许可。')
    measured=[(name,s) for name,s in component_rows if s.get('median') is not None]
    if measured:text.append('按已测中位数，最大的上述组成项为 **'+max(measured,key=lambda item:item[1]['median'])[0]+'**。组件可能属于不同层级；不将各项 p95/p99 相加并冒充实际端到端分位数。')
    environment=cpu.get('environment',{})
    text.append('下面使用科学部署解释器的独立 CPU profile：Python '+str(environment.get('python','未记录'))+'，NumPy '+str(environment.get('numpy','未记录'))+'，线程设置 '+str(environment.get('thread_env',{}))+'。较早 abs_env/NumPy 1.23.5 profile 原样保留，未混合两种环境的分位数。')
    if cpu.get('model_file_sha256'):text.append('实际模型 SHA256：'+json.dumps(cpu['model_file_sha256'],ensure_ascii=False)+'；冻结真实 X 文件 SHA256：'+str(cpu.get('feature_file_sha256','未记录'))+'。')
    for name,rows in cpu['models'].items():
        text+=['CPU '+name+'（真实冻结 '+str(cpu.get('feature_count','未记录'))+' 维 X、实际已训练模型）：']
        table=['| batch 候选数 | 首次调用 ms | warm 中位 ms | warm p95 ms | warm p99 ms | warm 最大 ms |',
               '|---:|---:|---:|---:|---:|---:|']
        for row in rows:
            s=row['warm_batched_predict_ms']
            table.append('| '+str(row['candidate_count'])+' | '+fmt(row['first_call_ms'])+' | '+' | '.join(fmt(s[k]) for k in ('median','p95','p99','maximum'))+' |')
        text.append('\n'.join(table))
        representative=next((r for r in rows if r['candidate_count']==8),rows[0])
        text.append('batch '+str(representative['candidate_count'])+'：CPU 输入复制 p95 '+fmt(representative['cpu_input_copy_ms']['p95'])+' ms；逐候选不批处理总推断中位 '+fmt(representative['unbatched_per_candidate_predict_total_ms']['median'])+' ms。首次模型加载 '+fmt(cpu.get('model_load_first_call_ms',{}).get(name))+' ms。')
    text.append('“首次调用”指加载后的该 batch 大小首次预测，不等于全进程冷启动。批处理/CPU 输入复制/逐候选开销均已分开保存。GPU 未测：本轮两类模型及训练实现均为 NumPy CPU 路径；不能推断 GPU 更快或更慢，也没有产生 GPU 传输数据。后台搜索负载可能造成离群值，原样保留。')
    jobs,pending,failed=unique_updates(updates)
    text+=['**17．一次 repetition-boundary 更新需要多久？**',stat_table([
        ('按模型 SHA/路径去重的实际模型生成 wall time',distribution(r['wall_s'] for r in jobs))],unit='s')]
    if not jobs:text.append('当前尚无 pilot 更新；离线训练各候选的耗时不能替代这一项。')
    else:text.append('共 '+str(len(jobs))+' 个唯一在线模型生成任务；offline prior 初始化不计入，update_prepared、下一边界 promotion 和 final_prepared 的重复日志不重复计数。pending 事件 '+str(len(pending))+'，失败/拒绝事件 '+str(len(failed))+'。')
    processing=[r['scientific_harness_inter_rep_processing_wall_s'] for session in (pilot or {}).get('sessions',[])
                for r in session.get('rows',[]) if r.get('scientific_harness_inter_rep_processing_wall_s') is not None]
    text+=['**18．学习/更新会阻塞连续执行吗？**',
           '活动模型在任务内保持不变；后台生成新版本，校验后仅在明确安全 repetition boundary 切换。模型未就绪时保留既有验证版本。model readiness wait 上限为 2 s；这不是整个 inter-repetition 延迟上限。返回提取、checkpoint、文件归档，以及单列的安全边界/下一次运行初始化也有成本。最终 pool.shutdown(wait=True) 属于收尾，不能描述为部署延迟保证。',
           stat_table([('科学 harness 的 inter-rep processing',distribution(processing))],unit='s'),
           '预算来源：5 ms 是原控制/采样周期，不是 learner deadline；已选 waypoint 通常持续远长于该周期。原 moving endpoint 有 40 ms bridge，并在观察到的 35 ms 已认证 fork 前决定接入主参考或不可逆制动；原始 source age 必须严格小于 100 ms。初始静止 OUTBOUND 首决策与 moving continuation 应分别分析。']
    overhead=roles.get('moving_continuation',{}).get('nonproducer_capture_to_activation_ms',{})
    if overhead.get('count'):
        text+=['同一请求逐项计算的 moving 非 producer 跨度（capture → activation 减去该请求实际 producer compute，保留采集/收集/最终验证等开销）：',
               stat_table([('moving 非 producer 实际配对跨度',overhead)]),
               '按其中已观察最大值，若其余开销保持现状，35 ms fork 留给 producer 的最小观察余量只有 '+fmt(max(0.,35.-overhead['maximum']))+' ms。此余量不是 WCET 保证，也不是各组件分位数之和；它进一步说明仅有算法 max <35 ms 不能满足完整主机 moving 窗口。']
    if gate:
        text.append('当前计算门状态：`'+gate.get('detailed_computation_status',gate['status'])+'`；algorithm plausible-path='+str(gate.get('algorithm_profile_within_preliminary_ceilings'))+'；正常模型 rollout 验证='+str(gate.get('clean_normal_model_rollout_validated'))+'；观察到的完整主机跨度均在对应机会内='+str(gate.get('observed_full_host_spans_within_architecture_opportunity'))+'。原 epoch replay 不含实时队列、新观察 handoff 复验和实际写入，故算法预算可行不等于完整主机 deadline 达标。')
        chosen=gate.get('selected_configuration',{})
        text.append('所选配置为首决策实际 '+str(chosen.get('first_pattern_candidate_count','未记录'))+' 候选，captured BANK 来源索引 '+str(chosen.get('proposal_source_indices','未记录'))+'，后续一个已提交 continuation，legacy proposal limit='+str(chosen.get('legacy_candidate_limit','未记录'))+'。这是 development capture 的有界 proposal prior；原硬筛选保留，既有 baseline/fallback 仍为迟到结果的权威处理路径。')
        if gate.get('moving_handoff_algorithm_directly_measured'):
            text+=['实际移动 committed continuation 参考速度 '+str(gate['continuation_snapshot_context'].get('captured_reference_velocity_rad_s'))+' rad/s；算法原 epoch 验证重复测量如下：',
                   stat_table([('实际 moving committed continuation 算法',gate['continuation_algorithm_profile']['algorithm_through_original_epoch_reference_validation_ms'])])]
            moving_components=gate['continuation_algorithm_profile'].get('components_ms',{})
            text+=['实际 moving 快照算法的进一步拆分（adapter 总计包含其 proposal、硬筛选、特征和 Q 项；不相加重复计数）：',
                   stat_table([(label,moving_components.get(key,{})) for key,label in (
                       ('decision_total_ms','adapter 决策到选择'),
                       ('adapter_return_to_escape_prepared_ms','选择返回 → 已认证 escape preparation'),
                       ('original_epoch_activation_validation_ms','原 epoch activation validator'))])]
            if not gate.get('ready_for_small_scientific_pilot'):
                text.append('当前计算门关闭，不能据此启动要求该门通过的在线改善 pilot；30 次 actual-moving 最大值超过严格 35 ms 机会。静止代理曾得到的 preliminary PASS 已保留并被版本化实际移动门取代；不删除离群值，也不通过重测挑选更小最大值。')
        if gate.get('continuation_snapshot_context',{}).get('captured_reference_stationary') is True:
            text.append('关键适用范围：RETURN 冻结快照虽然已提交 continuation，但参考速度为 [0,0]，是静止 RETURN 首段；其 28.602 ms 最大值只是 continuation 算法代理，不能称作直接测得 moving handoff 算法延迟。moving 完整主机跨度来自正常运行的实际 moving 请求；当前尚无移动快照离线算法重复测量。')
    if scaling:
        if any(replay.get('captured_phase')=='RETURN' and replay.get('captured_reference_stationary') is True for replay in scaling):
            text.append('RETURN 冻结快照参考速度为 [0,0]，属于静止已提交 continuation 代理；保留其缩放数据，但不将其用于实际移动算法门。')
        scaling_rows=[]
        for replay in scaling:
            label_prefix=str(replay.get('captured_phase'))+' '+('subset '+str(replay.get('proposal_source_indices')) if replay.get('proposal_source_indices') is not None else 'prefix')
            for row in replay.get('rows',[]):
                actual=sorted(set(row.get('observed_research_candidate_count',[])))
                label=label_prefix+' requested '+str(row['requested_research_candidate_count'])+' / actual '+str(actual)+' / legacy '+str(row.get('legacy_limit_label'))
                scaling_rows.append((label,row['algorithm_through_original_epoch_reference_validation_ms']))
        text+=['真实冻结快照的算法缩放（每项 30 次；原 epoch 参考验证，失败项另存原始结果；不含完整实时激活链）：',stat_table(scaling_rows),
               'RETURN 已提交 continuation 实际始终为一个候选；requested BANK 大小不代表该状态执行了同等候选数。首决策完整 10 个候选加 legacy1 的最大耗时超过 100 ms，因此不能用它宣称当前预算可行。所选四候选保留实际 development 已选优 descriptor，而不是未经测量地固定 prefix4。']
    if not gate:text.append('完整选型/正常运行计算门尚未生成；此处不制造 PASS。')
    text+=['**19．显式候选搜索 + Q 排序够快吗，是否需要 actor/distillation？**',
           '本轮优先依据实际正常运行与候选数缩放选择有限的多样首决策 proposal，以及后续一个已提交 continuation candidate。单候选 continuation 已不能继续通过减少研究候选数解决成本。若 Q 推断很小而硬筛选、原始候选比较、escape preparation、主线程收集或最终验证占主要时间，单纯增加 actor 不能解决这些成本。只有实际完整决策证据持续超出机会、且 proposal 数缩减仍不足时，再评价轻量 proposal policy，随后仍执行原有硬筛选；当前证据更支持先剖析这些调度/验证开销，不自动启动 actor。',
           '`RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS`。以上不构成硬件安全、WCET 或实时资格。']
    return '\n\n'.join(text)+'\n'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--cpu',type=Path,required=True);parser.add_argument('--gate',type=Path)
    parser.add_argument('--updates',type=Path);parser.add_argument('--pilot',type=Path)
    parser.add_argument('--scaling-profile',type=Path,action='append',default=[])
    parser.add_argument('--capture-profile',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    section=render_section(read_json(args.profile),read_json(args.cpu),
        gate=read_json(args.gate) if args.gate else None,updates=read_json(args.updates) if args.updates else None,
        pilot=read_json(args.pilot) if args.pilot else None,
        scaling=[read_json(path) for path in args.scaling_profile],
        capture_profile=read_json(args.capture_profile) if args.capture_profile else None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(section,encoding='utf-8')
    print(str(args.output))


if __name__=='__main__':main()
