"""Analytical cylinder-envelope decomposition; no native environment is created."""
import sys,time
import numpy as np
from acl2_shared import P,R,read,put,sha,utc
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage3.coupled import BED_HEIGHT_M,SLEEVE_HALF_LENGTH_M,SLEEVE_OUTER_RADIUS_M
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1

def main():
    start=time.time();belief=read('history/CAUSAL_COMMISSIONED_BELIEF.json')
    g=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in belief['geometry'].items()});env=RigidTableReferenceEnvelopeV1(g)
    px,pz=g.plane_x_world[2],g.plane_z_world[2];L=SLEEVE_HALF_LENGTH_M;r=SLEEVE_OUTER_RADIUS_M
    def components(q):
        phi=q[0]-q[1];a=np.cos(phi)*px+np.sin(phi)*pz
        smooth=float(env.cuff_centers(q)[0,2]-r*np.sqrt(1-a*a)-BED_HEIGHT_M)
        return smooth,float(-L*abs(a)),float(a)
    cases=[]
    paths=['audit/ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json','audit/PPO_ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json']
    for path in paths:
        d=read(path);q,dq=np.split(np.asarray(d['causal_estimated_state']),2);phi=q[0]-q[1];v=dq[0]-dq[1]
        smooth0,cusp0,a0=components(q);ap=(-np.sin(phi)*px+np.cos(phi)*pz)*v;app=-a0*v*v
        thighaxis=np.cos(q[0])*px+np.sin(q[0])*pz
        smooth_analytic=-g.thigh_length_m*thighaxis*dq[0]**2+g.cuff_distance_m*app+r*(ap*ap/(1-a0*a0)**1.5+a0*app/np.sqrt(1-a0*a0))
        same_branch=smooth_analytic-L*np.sign(a0)*app
        sweep=[]
        for original in d['stencil_sweep']:
            h=original['time_stencil_s'];sp,cp,azp=components(q+h*dq);sm,cm,azm=components(q-h*dq)
            smooth_fd=(sp-2*smooth0+sm)/(h*h);cusp_fd=(cp-2*cusp0+cm)/(h*h)
            linearized=-L*(abs(a0+h*ap)-2*abs(a0)+abs(a0-h*ap))/(h*h)
            sweep.append(dict(h_seconds=h,original_curvature=original['curvature_m_s2'],smooth_FD=smooth_fd,endpoint_minimum_FD=cusp_fd,linearized_endpoint_minimum_FD=linearized,components_sum=smooth_fd+cusp_fd,decomposition_residual=original['curvature_m_s2']-smooth_fd-cusp_fd,crosses_endpoint_branches=azm*azp<0))
        native=next(x for x in sweep if x['h_seconds']==1e-5)
        cases.append(dict(attempt_id=d['attempt_id'],q_rad=q,dq_rad_s=dq,axis_z=a0,axis_z_rate_per_s=ap,linearized_crossing_stencil_seconds=abs(a0/ap),same_branch_analytic_curvature_m_s2=same_branch,original_guard_h_seconds=1e-5,native_stencil=native,sweep=sweep,input_sha256=sha(P/path)))
    passed=all(abs(c['native_stencil']['decomposition_residual'])<1e-4 and c['native_stencil']['crosses_endpoint_branches'] and abs(c['native_stencil']['endpoint_minimum_FD'])>1000*abs(c['same_branch_analytic_curvature_m_s2']) for c in cases)
    result=dict(status='PASS' if passed else 'REVIEW_REQUIRED',utc=utc(),native_steps=0,physical_attempts=0,formula='gap(q)=cuff_center_z(q)-radius*sqrt(1-axis_z(q)^2)-bed_height-half_length*abs(axis_z(q))',geometry=dict(sleeve_half_length_m=L,sleeve_radius_m=r),cases=cases,interpretation='The enormous original numerical curvature is almost entirely the endpoint-minimum cusp term, rather than smooth rigid-body curvature. This decomposes the exact original computation, not the true physical limb acceleration.',exact_cusp_limit='At axis_z=0 and nonzero axis_z_rate, centered endpoint-minimum second difference is asymptotically -2*half_length*abs(axis_z_rate)/h. At the observed nonzero offsets, h below the crossing scale stays on one branch; no divergence as h tends to zero is claimed for those offset states.',future_hypothesis='The min-gap constraint is algebraically equivalent to requiring both smooth endpoint gaps above the identical threshold. A two-branch causal feedback formulation may avoid spurious cross-branch second differentiation; feasibility, safety invariance, native motion and force must be separately validated. No replacement was implemented or tested here.',source_sha256=sha(__file__),wall_s=time.time()-start)
    put('audit/CLEARANCE_CUSP_ANALYTIC_DECOMPOSITION.json',result)
    lines=['# 原clearance包络的解析机制核验','','本分析新增物理尝试和native积分均为0。没有修改控制器、几何、安全阈值或scorer。','','原袖套下边界可写为 `gap(q)=z_cuff(q)-r*sqrt(1-a(q)^2)-z_bed-L*abs(a(q))`，其中 `a` 是袖套轴的世界竖直分量。前三项在本次近水平姿态附近光滑，最后的端点最小值在 `a=0` 不可微。','','|实际失败案例|原10μs差分曲率 m/s²|端点最小值项|光滑项|同分支解析曲率|跨分支临界h μs|','|---|---|---|---|---|---|']
    for c in cases:
        n=c['native_stencil'];lines.append(f"|{c['attempt_id']}|{n['original_curvature']:.6f}|{n['endpoint_minimum_FD']:.6f}|{n['smooth_FD']:.6f}|{c['same_branch_analytic_curvature_m_s2']:.6f}|{1e6*c['linearized_crossing_stencil_seconds']:.6f}|")
    lines+=['','在精确切换点，若轴竖直速度非零，端点项的中心二阶差分约为 `-2L*abs(a_dot)/h`。已观察事件处并非精确零点；h小于表中跨分支尺度后回到单分支，不能称这些固定偏置状态在h→0时发散。极小h还会出现浮点抵消。','','这解释原控制器计算中的大负曲率及随后的力矩修正，不把该数值称为真实Human加速度，也不删除因此产生的native jerk。原函数因果重放、真实冲量和后续运动失败另有各自证据。','','待验证的下一步：`min(gap_a,gap_b)>=margin` 与同时满足两个端点gap约束代数等价。可在独立协议中研究两条光滑分支的因果反馈是否避免跨分支二阶差分，同时保持相同几何、阈值和原scorer。此处未实现或实测该替代方案，不声称安全或收益已证明。','','完整参数、原输入SHA和各h分解见 [机器可读结果](audit/CLEARANCE_CUSP_ANALYTIC_DECOMPOSITION.json)。']
    (P/'CLEARANCE_CUSP_ANALYTIC_NOTE.md').write_text('\n'.join(lines)+'\n')
    print('CLEARANCE_CUSP_ANALYTIC',result['status'],[{k:c['native_stencil'][k] for k in ['original_curvature','endpoint_minimum_FD','smooth_FD','decomposition_residual']} for c in cases],flush=True)

if __name__=='__main__':main()
