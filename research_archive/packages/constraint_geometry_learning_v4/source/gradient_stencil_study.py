from pathlib import Path
import os,sys,json
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'source'),str(P/'runtime/control'),str(P/'runtime/code')]
import numpy as np
from endpoint_study import endpoints,ENV,G
from acl2_shared import put
rows=[]
for ident in ['CORE_C_019','PPO_SCRATCH_TRAIN_0009']:
 d=json.loads((P.parent/'representation_execution_v3/analysis/forensics'/(ident+'.json')).read_text());s=np.array(d['event_state']);q=s[:2];dq=s[2:];c=d['guard'];ep=endpoints(q,dq);eps=1e-5;basis=np.eye(2)*eps;grad=(ENV.margins(q[None,:]+basis)['sleeve_m']-ENV.margins(q[None,:]-basis)['sleeve_m'])/(2*eps);axis=lambda q:float(G.plane_x_world[2]*np.cos(q[0]-q[1])+G.plane_z_world[2]*np.sin(q[0]-q[1]));cross=[axis(q+b)*axis(q-b)<0 for b in basis];replacement=min(e['curvature'] for e in ep);a=np.array(c['requested_acceleration_rad_s2']);shortfall=max(0.,c['required_gap_acceleration_m_s2']-float(grad@a)-replacement)
 rows.append(dict(id=ident,gradient_step_rad=eps,directional_step_s=eps,gradient_stencil_crosses_per_joint=cross,original_gradient=grad,original_gradient_replay_max_error=float(np.max(abs(grad-np.array(c['model_gap_gradient_m_rad'])))),endpoint_gradients=[e['gradient'] for e in ep],original_curvature=c['model_curvature_m_s2'],endpoint_curvatures=[e['curvature'] for e in ep],curvature_only_arithmetic_intervention=dict(unchanged_gradient=grad,unchanged_requested_acceleration=a,replacement_curvature=replacement,resulting_shortfall=shortfall,correction_would_be_zero=shortfall==0,physical_application=False),scope='Exact old function terms; curvature-only arithmetic intervention. No physical guard replacement or unique physical mediation proof.'))
put('analysis/GRADIENT_STENCIL_STUDY.json',dict(status='EXECUTED_ZERO_PHYSICS',rows=rows,new_native_steps=0));print([(r['id'],r['gradient_stencil_crosses_per_joint'],r['curvature_only_arithmetic_intervention']['resulting_shortfall']) for r in rows])
f=P/'CLEARANCE_GEOMETRY_ANALYSIS.md';s=f.read_text();s+='\n## 关节梯度模板与曲率模板分开\n\nC19和PPO第9次的两个q±10⁻⁵rad关节梯度模板也跨端点分支，原梯度逐项精确复现。水平轴局部可写成∇g_FD≈∇smooth−L·clip(φ/ε_q,−1,1)(1,−1)，是在较宽q模板内对端点法向进行数值平均；这不等于同时保护两端点。相较之下方向曲率模板的关节幅度是h·dq，二者带宽和单位不同。固定原gradient、a_requested、因果gap/rate，只在算术中把曲率替换为单端点曲率，两例shortfall都变0；直接确认该局部控制修正的计算触发来自方向曲率项。此算术干预没有应用于物理，独占物理中介归因仍未建立。详情analysis/GRADIENT_STENCIL_STUDY.json。\n';f.write_text(s)
