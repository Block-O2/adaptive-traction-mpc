from pathlib import Path
import sys,time,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_jitter_m2_host_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc
from native_interface_adapter import native,rotvec,rotvec_fast,Rotation
from traction_mpc_stage3.spring_damper_interface import AttachmentState,InterfaceParameters
from traction_mpc_stage5.full3d_adaptive_integration_v1.fast_interface import ExactInterfaceEvaluator
def main():
 version=sys.argv[1] if len(sys.argv)>1 else 'N2'
 callback=rotvec_fast if version.startswith('N3') else rotvec
 rng=np.random.default_rng(137);errors=np.zeros(10);times=[];baseline=[]
 p=InterfaceParameters((6000.,6000.,6000.),(120.,120.,120.),5.,.1,(.001,0.,0.),(.02,-.01,0.))
 cap=native.create(np.asarray(p.translation_stiffness_n_m),np.asarray(p.translation_damping_ns_m),np.asarray(p.rest_translation_human_m),Rotation.from_rotvec(p.rest_rotation_rotvec_human_rad).as_matrix(),p.rotation_stiffness_nm_rad,p.rotation_damping_nms_rad);e=ExactInterfaceEvaluator()
 for i in range(1000):
  r=AttachmentState(rng.normal(size=3)*.01,Rotation.from_rotvec(rng.normal(size=3)*(.001 if i<100 else 1.)).as_matrix(),rng.normal(size=3)*.1,rng.normal(size=3)*.1)
  h=AttachmentState(rng.normal(size=3)*.01,Rotation.from_rotvec(rng.normal(size=3)*(.001 if i<100 else 1.)).as_matrix(),rng.normal(size=3)*.1,rng.normal(size=3)*.1)
  state=np.r_[r.position_world_m,r.rotation_world.ravel(),r.angular_velocity_world_rad_s,r.velocity_world_m_s,h.position_world_m,h.rotation_world.ravel(),h.angular_velocity_world_rad_s,h.velocity_world_m_s]
  t=time.monotonic_ns();expected=e.evaluate(p,r,h);baseline.append(time.monotonic_ns()-t)
  t=time.monotonic_ns();actual=native.evaluate_arrays(cap,state,callback);times.append(time.monotonic_ns()-t)
  for j,(x,y) in enumerate(zip(vars(expected).values(),actual)):errors[j]=max(errors[j],float(np.max(np.abs(np.asarray(x)-np.asarray(y)))))
  assert native.evaluate_arrays(cap,state,callback) is actual,'same full input cache identity'
 assert np.max(errors)<=1e-10,errors
 out=dict(status='PASS',no_physics=True,inputs=1000,max_errors=errors.tolist(),original_ms=float(np.median(baseline)/1e6),native_ms=float(np.median(times)/1e6),atol=1e-10,fast_math=False,float64=True,original_scipy_SO3=True)
 sc.save(version+'_NATIVE_LOCAL_REGRESSION.json',out);print(out)
if __name__=='__main__':main()
