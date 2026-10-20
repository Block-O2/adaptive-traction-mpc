from pathlib import Path
import json,time,hashlib,sys
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
load=lambda p:json.loads(Path(p).read_text())
selected=load(S/'FROZEN_SELECTION.json');best=selected['best'];m=load(best['metrics_path']);b=load(S/'reports'/(best['base_id']+'_MEASURED.json'));v=load(S/'PHYSICAL_FEASIBILITY_VALIDATION.json');abl=load(S/'INTERFACE_ABLATIONS.json');decision=load(S/'FINAL_DECISION.json');x=best['candidate']['free_parameters']
assert max(abs(q) for q in best['candidate']['normalized_parameters'])<=1+1e-12
fields=[]
if any(abs(x[i])>1e-12 for i in [0,5]):fields.append('已有请求上的有界 common-progress scalar（与反对称delta分开）')
if any(abs(x[i])>1e-12 for i in [3,4,8,9]):fields.append('已有内部路点上的独立 hip/knee pass-through velocity scale/skew 或等价dq pair')
proposal='；'.join(fields)
abtable=['|冻结消融|完整J_F N·s|相对B降低%|运动资格|相对冻结最好增加J_F N·s|','|---|---:|---:|---|---:|']
for r in abl['rows']:abtable.append(f"|{r['candidate']['id']}|{r['J_F_N_s']:.6f}|{r['comparison']['gain_percent']:.6f}|{'PASS' if r['comparison']['acceptance_pass'] else 'FAIL'}|{r['J_F_N_s']-best['J_F_N_s']:.6f}|")
gap=(S/'INTERFACE_GAP_ANALYSIS.md').read_text()
gap+='\n## 同条件冻结消融与最小能力\n\n'+'\n'.join(abtable)+f'''\n\n实际冻结最好运动使用：{proposal}。已有反对称delta仍可以表达差分位置项；共同进度和独立通过速度不能由当前raw-v2单值接口直接指定。它们是在同一完整物理模型中使用合法机器人力矩前向执行，未修改Human或接触。消融是已冻结参考的因果诊断，不是所有原生B序列的最优搜索，因此不能声称原生B绝对无法近似任何类似运动。\n\n最小后续研究提议仅限上述已使用字段，保持HOLD/端点零调整、scheduler/continuous clearance/current-state admission、C2 bridge、100ms生命周期、安全和fallback。独立速度对是原scheduler已有的数据结构，本轮只扩展离线参考意图。正式B没有合并这些字段。\n\n验证范围包含完整冻结OUTBOUND和预先规定native RETURN0之后的冻结R1+；原最佳的R0自由调整被条件前缀消耗，不冒称原全串动作在新条件下完全复现。\n'''
(S/'INTERFACE_GAP_ANALYSIS.md').write_text(gap)
table=['|原生实际运动统计|Hip最好|Hip B|Knee最好|Knee B|最差比值|冻结规则|','|---|---:|---:|---:|---:|---:|---|']
for signal,stats in [('velocity_deg_s',['max_abs','p95_abs','rms']),('acceleration_deg_s2',['max_abs','p95_abs','rms']),('jerk_deg_s3',['p95_abs','rms','max_abs'])]:
    for stat in stats:
        a=m['motion']['raw']['full'][signal][stat];ref=b['motion']['raw']['full'][signal][stat];ratio=max(a[i]/ref[i] for i in [0,1]);rule='仅诊断' if signal=='jerk_deg_s3' and stat=='max_abs' else '≤1.1'
        table.append(f'|{signal}/{stat}|{a[0]:.6f}|{ref[0]:.6f}|{a[1]:.6f}|{ref[1]:.6f}|{ratio:.6f}|{rule}|')
validation_table=['|新合法条件|配对方案|J_F N·s|相对本条件B降低%|完整任务/运动条件|失败项|','|---|---|---:|---:|---|---|']
for r in v['rows']:
    validation_table.append(f"|{r['id'].split('_')[0]}|{r['candidate']['id']}|{r['J_F_N_s']:.6f}|{r['comparison']['gain_percent']:.6f}|{'PASS' if r['comparison']['acceptance_pass'] else 'FAIL'}|{', '.join(r['comparison']['failed_requirements']) or '无'}|")
body=(S/'REPORT.md').read_text()
body+='\n## 完整原生运动数值\n\n'+'\n'.join(table)+'\n\n速度单位deg/s，加速度deg/s²，jerk deg/s³。以上用全部native true dq，原生0.25ms间隔、raw梯度，不删除端点或以滤波显示替代。\n\n'
body+=f"行程差 Hip/Knee={best['comparison']['excursion_delta_deg']}°；累计角位移比={best['comparison']['cumulative_ratio']}；phase/endpoint最大偏差={best['comparison']['phase_boundary_max_delta_deg']:.9f}°；阶段形状最大差={best['comparison']['phase_shape_max_delta_deg']:.6f}°（不宣称治疗等效）。tracking RMS最好={m['tracking_RMS_deg']}°，B={b['tracking_RMS_deg']}°。\n\n"
body+=f"完整及各phase时长：最好 {m['phase_durations']}，B {b['phase_durations']}；完整native运动时长 {m['dose']['duration_s']:.6f}s。moment integral最好/B={m['moment_integral_Nm_s']:.6f}/{b['moment_integral_Nm_s']:.6f} N·m·s；force peak={m['force_peak_N']:.6f}/{b['force_peak_N']:.6f}N；moment peak={m['moment_peak_Nm']:.6f}/{b['moment_peak_Nm']:.6f} N·m。原absolute原生安全轴全部通过。\n\n"
body+='## 冻结独立条件结果\n\n'+'\n'.join(validation_table)+'\n\n'
body+='两条件均从合法完整OUTBOUND入口fork，实际执行冻结的完整OUTBOUND，再执行共享native-only RETURN0条件前缀，后续R1+继续冻结参数。初始完整状态同条件配对一致；不同实际RETURN1状态由真实前向运动产生，没有qpos/qvel设置。原R0动作被条件消费，不能冒称全串原动作未见测试。\n\n'
body+=f"真实RETURN1跨条件最大状态差：{v['actual_state_difference']}。这是同一Human的状态扰动，非不同患者。参数冻结时刻 {selected['unix']}，没有验证反馈选参。扩展验证覆盖的修订早于参数冻结和任何W输出，原协议版本保留，主运动规则/任务/动力学/预算未改变。\n\n"
body+='## 接口字段消融\n\n'+'\n'.join(abtable)+f'\n\n候选最小后续接口：{proposal}。消融不重新选参，完整阴性结果也保留。\n\n'
body+='优化器子进程从COBYLA回调返回继承的物理runtime时，会打印预期的callback unwind文本；父优化器等待完整物理子进程后继续。这不是MuJoCo数值失败。实际优化终态及未收敛记录保留在OPTIMIZER_STATUS.jsonl，不能将有限可行观察称为全局最优或优化收敛。\n\n'
body+='![Force and motion](figures/FORCE_MOTION_SEARCH.png)\n\n'
(S/'REPORT.md').write_text(body)
teacher=dict(status='NOMINAL_HUMAN_OFFLINE_TEACHER_PROTOTYPE',level='DYNAMICS_FEASIBLE',selected_id=best['id'],full_J_F_N_s=best['J_F_N_s'],gain_percent=best['comparison']['gain_percent'],original_B_same_condition_J_F_N_s=b['J_F_N_s'],candidate=best['candidate'],scope='Exact nominal complete trajectory with original physical system; full O plus conditioned R1+ tests separately. Not a native B policy, clinical qualification or cross-human teacher.',actual_motion_trace=str(S/'motion_series'/(best['id']+'.npz')),actual_control_trace=str(S/'source/results'/best['id']/'trace.npz'),actual_receipt_evidence=str(S/'reports'/(best['id']+'_EXECUTED_RESIDUAL_RECEIPTS.json')),interface_gap='Existing Neural Q raw K3 cannot directly realize the common-progress/dq pair fields; a future learning action contract would need explicit separate versioning.',no_Q_training=True,parameter_sha256=hashlib.sha256((S/'FROZEN_SELECTION.json').read_bytes()).hexdigest())
(S/'BEST_TRAJECTORY_TEACHER.json').write_text(json.dumps(teacher,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(best=best['id'],gain_percent=best['comparison']['gain_percent'],recommended_direction=decision['direction'],interface_fields=fields)))
