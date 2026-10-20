from pathlib import Path
import sys,numpy as np,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_overnight_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc
from native_interface_adapter import native,rotvec,rotvec_fast,Rotation
from native_vectors import cross
def main():
 rng=np.random.default_rng(1764);errors=[];exact=0;lat=[];base=[]
 angles=[0.,1e-12,1e-3-1e-15,1e-3,1e-3+1e-15,np.pi-1e-12,np.pi,np.pi+1e-12]
 matrices=[np.eye(3),np.diag([1.,1.,-1.]),np.zeros((3,3)),np.eye(3)*.9,np.eye(3)+np.array([[0.,1e-11,0.],[0.,0.,0.],[0.,0.,0.]])]
 for i in range(2000):
  axis=rng.normal(size=3);axis/=np.linalg.norm(axis);angle=angles[i%len(angles)] if i<160 else rng.uniform(-4.,4.);matrices.append(Rotation.from_rotvec(axis*angle).as_matrix())
 for matrix in matrices:
  try:
   t=time.monotonic_ns();expected=rotvec(matrix);base.append(time.monotonic_ns()-t)
  except ValueError:
   try:rotvec_fast(matrix)
   except ValueError:continue
   raise AssertionError('SO3 native failed to retain rejection')
  t=time.monotonic_ns();actual=rotvec_fast(matrix);lat.append(time.monotonic_ns()-t);errors.append(float(np.max(np.abs(actual-expected))));exact+=int(np.array_equal(actual,expected))
 assert max(errors)==0.,max(errors)
 for i in range(2000):
  a=rng.normal(size=3);b=rng.normal(size=3)
  assert np.array_equal(cross(a,b),np.cross(a,b))
 for a,b,kw in [(np.ones((4,3)),np.zeros((4,3)),{}),(np.ones(3,dtype='float32'),np.zeros(3,dtype='float32'),{}),(np.ones(2,dtype='int64'),np.zeros(2,dtype='int64'),{}),(np.ones((3,4)),np.zeros((3,4)),{'axis':0})]:
  assert np.array_equal(cross(a,b,**kw),np.cross(a,b,**kw))
 out=dict(status='PASS',no_physics=True,SO3_cases=len(matrices),bit_exact_count=exact,max_SO3_error=max(errors),source='Installed SciPy 1.15.3 operation order; determinant/SVD/error original fallback outside conservative orthogonality interior',source_url='https://github.com/scipy/scipy/blob/v1.15.3/scipy/spatial/transform/_rotation.pyx',cross_cases=2000,original_ms=float(np.median(base)/1e6),native_ms=float(np.median(lat)/1e6),not_new_rotation_algorithm=True)
 sc.save('N3_SO3_VECTOR_LOCAL_REGRESSION.json',out);print(out)
if __name__=='__main__':main()
