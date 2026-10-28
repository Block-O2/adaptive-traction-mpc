"""Read-only source/evidence mechanism audit; no integration or policy changes."""
from pathlib import Path
import json,math
from research_common import ROOT,RUNTIME,read,atomic,sha,now
cases=read(ROOT/'audit/H2_R1_COMPARISON.json')['cases'];results=[]
for c in cases:
 p=Path(c['run'])/'env/episode_0001/online_tick_evidence.jsonl';ts=[json.loads(s) for s in p.read_text().splitlines()];phases={}
 for a,b in zip(ts,ts[1:]):
  dt=b['task_s']-a['task_s'];part=phases.setdefault(a['phase'],dict(duration_s=0.,force_norm_axis_partition_N_s=[0.,0.,0.],moment_norm_axis_partition_Nm_s=[0.,0.,0.]));part['duration_s']+=dt
  for key,out in [('measured_force_world_n','force_norm_axis_partition_N_s'),('measured_moment_world_nm','moment_norm_axis_partition_Nm_s')]:
   v=a[key];norm=math.sqrt(sum(x*x for x in v))
   if norm>0:part[out]=[x+y*y/norm*dt for x,y in zip(part[out],v)]
 jf=sum(sum(x['force_norm_axis_partition_N_s']) for x in phases.values());jm=sum(sum(x['moment_norm_axis_partition_Nm_s']) for x in phases.values());assert abs(jf-c['motion']['JF'])<1e-7 and abs(jm-c['motion']['JM'])<1e-7
 results.append(dict(seed=c['seed'],branch=c['branch'],phases=phases,source=str(p),source_sha256=sha(p)))
paths=[RUNTIME/'source/stages/stage3_full3d/src/traction_mpc_stage3/spring_damper_interface.py',RUNTIME/'source/stages/stage3_full3d/src/traction_mpc_stage3/interface_measurement_contract.py',RUNTIME/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/fast_interface.py']
atomic(ROOT/'audit/CUFF_TRADEOFF_MECHANISM.json',dict(time_utc=now(),cases=results,definition='Norm-axis partition integral Σ F_i²/||F|| dt sums exactly to original norm integral; descriptive directional accounting, not causal attribution',source_sha256={str(p):sha(p) for p in paths},constitutive_equations=dict(force='R_H (K x + D u)',sensor_moment_at_robot_site='R_H (k_r theta + d_r omega)',human_site_moment='sensor pure couple + r cross force'),direct_evidence='Original sensor boundary transmits the negative robot reaction about adapter_cuff_site. Translation and rotation channels are distinct; reduced force norm does not imply reduced moment norm.',unresolved='No isolated proof that spring vs damping, posture, phase coordination, optimizer, or a particular reward term uniquely caused changes. Do not explain measured robot-site moment solely by a changing force lever arm.',new_physics=0,Adam=0))
p=ROOT/'H2_R1_COMPARISON.md';text='''
## 原cuff测量点与构成关系

只读源码核对：原Kelvin–Voigt物理中 `F = R_H(Kx+Du)`，独立旋转couple为 `R_H(k_r theta+d_r omega)`；robot-facing sensor按原约定读取**adapter_cuff_site**处的transmitted wrench。Human-site moment另含`r×F`，不能把两个参考点混用。原接口分别含平移/线速度与旋转/角速度通道，因此降低JF不必降低JM。

保存5ms向量的范数分量分摊已独立重算，逐phase与原JF/JM求和一致，见 `audit/CUFF_TRADEOFF_MECHANISM.json`。它定位传感器方向上的变化，没有改变scorer；不能单凭这些积分把旋转弹簧、阻尼、姿态或某个Reward项确定为唯一原因，也不能将robot-site moment增加直接归因为力臂变大。
'''
if '## 原cuff测量点' not in p.read_text():p.write_text(p.read_text()+text)
print('source-bound cuff mechanics and directional dose audit saved')
