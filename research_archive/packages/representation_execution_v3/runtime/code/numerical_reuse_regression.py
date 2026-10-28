from pathlib import Path
import sys,numpy as np,pickle,time
S=Path('/home/hank/ihear-lab/representation_execution_v3/runtime');sys.path.insert(0,str(S/'code'))
import study_common as sc,numerical_reuse as reuse
from scipy.spatial.transform import Rotation
def main():
 cached,original=reuse.install(shadow=True);rng=np.random.default_rng(1379);lat=[];base=[];invalidations=0
 for i in range(100):
  kw=dict(attachment_position_m=rng.normal(size=3),attachment_rotation_matrix=Rotation.from_rotvec(rng.normal(size=3)).as_matrix(),attachment_velocity_m_s=rng.normal(size=3),attachment_angular_velocity_rad_s=rng.normal(size=3),robot_q_rad=rng.normal(size=6),robot_dq_rad_s=rng.normal(size=6),neutral_robot_q_rad=rng.normal(size=6),target_position_m=rng.normal(size=3),target_velocity_m_s=rng.normal(size=3),target_rotation_matrix=Rotation.from_rotvec(rng.normal(size=3)).as_matrix(),target_angular_velocity_rad_s=rng.normal(size=3),robot_attachment_jacobian=rng.normal(size=(6,6)),bias_torque_nm=rng.normal(size=6),torque_limits_nm=np.full(6,200.))
  token=reuse.SCOPE.set((1,'model_v1',i*.005))
  try:
   expected=original(**kw);out=cached(**kw);assert pickle.dumps(out,protocol=5)==pickle.dumps(expected,protocol=5)
   assert cached(**kw) is out
   for name in kw:
    changed={k:v.copy() for k,v in kw.items()};changed[name].flat[0]+=1e-6
    actual=cached(**changed);expected=original(**changed);assert pickle.dumps(actual,protocol=5)==pickle.dumps(expected,protocol=5);invalidations+=1
   reuse.SCOPE.set((2,'model_v1',i*.005));assert cached(**kw) is not out
  finally:reuse.SCOPE.reset(token)
 out=dict(status='PASS',no_physics=True,fixed_cases=100,dependency_mutations=invalidations,ownership_version_timestamp_in_key=True,all_original_validation_retained=True,rows=reuse.ROWS,scope='Explicit prepared executable numerical context only; full loaded context/model/Jacobian/safety still evaluated fresh')
 sc.save('R2_NUMERICAL_REUSE_LOCAL_REGRESSION.json',out);print(out)
if __name__=='__main__':main()
