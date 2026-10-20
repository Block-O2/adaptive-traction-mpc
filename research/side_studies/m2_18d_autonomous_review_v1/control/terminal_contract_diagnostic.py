"""Quantify final approach contracts without changing admission or controller."""
from pathlib import Path
import os,json,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return clean(x.tolist())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
chain=json.loads((P/'derived/N2_TRACKING_CHAIN.json').read_text());motion=json.loads((P/'derived/N2_MECHANISM.json').read_text());rows=[]
for arm,schedules in chain['schedules'].items():
 out=[s for s in schedules if s['phase']=='OUTBOUND'];last=out[-1];before=out[-2];d=np.asarray(last['target_q_deg'])-last['start_q_deg'];v=np.asarray(last['start_dq_deg_s']);T=last['duration_s'];ratio=np.divide(v*T,d,out=np.full(2,np.nan),where=abs(d)>1e-8);stop=np.divide(v*v,2*abs(d),out=np.full(2,np.nan),where=abs(d)>1e-8)
 m=motion['measures'][arm]
 rows.append(dict(arm=arm,last_request_task_s=last['request_task_s'],last_duration_s=T,desired_distance_deg=d,start_reference_velocity_deg_s=v,v0_times_duration_over_distance=ratio,constant_deceleration_necessary_bound_deg_s2=stop,prior_free_status=before['free_status'],prior_target_q_deg=before['target_q_deg'],prior_target_dq_deg_s=before['target_dq_deg_s'],actual_knee_full_peak=m['knee_peak'],full_issued_reference_max_abs_accel_deg_s2=m['reference_max_abs_acceleration_deg_s2'],actual_knee_acceleration_ratio_vs_B=m['knee_acceleration_max_ratio_vs_B'],actual_velocity_TV_deg_s=m['actual_velocity_TV_deg_s']))
put('derived/TERMINAL_CONTRACT_DIAGNOSTIC.json',dict(status='COMPUTED',unix=time.time(),rows=rows,scientific_scope='Observed target saturation/rejection, final schedule geometry and closed-loop outcomes; not a proof of a single causal mediator.',kinematic_bound_scope='v0²/(2d) is a necessary max-acceleration bound for monotone stopping in remaining reference distance with no overshoot, not the actual quintic peak or an actual Human prediction; zero-distance channels are null.',automatic_filter=False,new_physics=0))
table='\n'.join(f"|{r['arm']}|{r['last_request_task_s']:.3f}|{r['last_duration_s']:.3f}|{r['desired_distance_deg'][1]:.6f}|{r['start_reference_velocity_deg_s'][1]:.6f}|{r['full_issued_reference_max_abs_accel_deg_s2'][1]:.6f}|{abs(r['actual_knee_full_peak']['value_deg_s2']):.6f}|" for r in rows)
text='''# N2终末接近与闭环结构诊断

本轮N2原B/18D完整trace、native物理与receipt已与资格包逐字段精确匹配，原失败可复现。主候选C去除了三个去程速度偏置，但没有减小实际膝加速度；它改变前段的目标、通过状态和请求时序，之后原native B在新的状态上重新选目标与终端速度。

|臂|最后OUT请求task s|最后suffix时长s|最后膝参考距离°|起始膝参考速度°/s|全程issued膝amax°/s²|实际膝amax°/s²|
|---|---:|---:|---:|---:|---:|---:|
'''+table+'''

原E倒数第二个去程目标已有hip=120°、knee约117.7845°；free intent因NORMALIZED_TARGET_OUT_OF_RANGE被拒，保留原B已筛查目标。C同样在该处被拒，但knee目标约117.4911°，原native终端速度变成10.0358°/s（E为8.8623°/s）；最终stop suffix从E的0.220s变为C的0.235s，最后请求推迟约0.345s。这里的参考速度上升不是新速度参数偷偷改变，而是原native规则对改变后的因果目标/状态作出的响应。

C的全程issued膝加速度峰比E低，但实际峰反而更高；实际TV_v也没有因去除显式速度偏置自动降低。本包诊断TV_v/TV_a是分别按hip、knee计算的L1总变差数组；历史报告的combined Euclidean TV另有定义，不直接混算百分比。该闭环干预反驳了本轮简单消融假设，不证明某个参考峰、allocator分量或短suffix独自致因。R及其重复的完整结果另按原门审查。原E和C的失败都不允许通过放宽motion或安全阈值取消。

最小下一设计应围绕“单关节先到goal时，协调意图被原范围门拒绝→后续原目标与native通过速度→短终末suffix→实际闭环制动”的可执行合同。先对原允许的因果target/reference与末段停止几何作离线数学重建，固定一个边界连续的协调意图族；只改Side Study候选生成，仍交由原certificate/40ms桥/current admission/100ms lifecycle执行。再用极少量同父完整配对，观察全程motion/force，而非只优化局部TV或事后为每个失败状态补丁。该设计没有在本轮被物理验证，也不构成可部署风险筛选器。
'''
(P/'MECHANISM_FINDINGS.md').write_text(text)
print('TERMINAL_CONTRACT_DIAGNOSIS',[(r['arm'],r['last_duration_s'],r['actual_knee_acceleration_ratio_vs_B']) for r in rows])
