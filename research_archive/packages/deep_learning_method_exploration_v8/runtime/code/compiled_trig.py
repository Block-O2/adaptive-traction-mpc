"""Compile only the existing interval Taylor polynomial; retain original cache."""
from task_bootstrap import *
import ctypes,numpy as np
from functools import lru_cache
from compiled_interval import SOURCE
SOURCE=SOURCE+r'''
extern "C" int trig_bounds(double lo,double hi,int cosine,const double*t,double*out){
 try{I r=trig(I(lo,hi),cosine!=0,t);out[0]=r.lo;out[1]=r.hi;return 1;}catch(...){return -1;}
}
'''
ORIGINAL=None;LIB=None;COEFS=None;SHADOW=False;ROWS=[]
def build():
 folder=STUDY/'compiled_trig';folder.mkdir(exist_ok=True);source=folder/'trig.cpp';source.write_text(SOURCE);identity=hashlib.sha256(SOURCE.encode()).hexdigest();target=folder/(identity+'.so');flags=['-std=c++17','-O2','-shared','-fPIC','-fno-fast-math','-ffp-contract=off','-frounding-math']
 if not target.exists():subprocess.run(['g++',*flags,str(source),'-o',str(target)],check=True,capture_output=True)
 save(folder/'BUILD.json',dict(source_sha256=identity,binary_sha256=sha(target),compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],flags=flags,no_installation=True,no_model_input_prewarm=True))
 return target
def install(shadow=False):
 global ORIGINAL,LIB,COEFS,SHADOW
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as m
 if ORIGINAL is None:ORIGINAL=m._trig_bounds
 if LIB is None:
  LIB=ctypes.CDLL(str(build()));p=np.ctypeslib.ndpointer(dtype=np.float64,ndim=1,flags='C_CONTIGUOUS');LIB.trig_bounds.argtypes=[ctypes.c_double,ctypes.c_double,ctypes.c_int,p,p];LIB.trig_bounds.restype=ctypes.c_int
  COEFS=np.asarray([*[n for coef in (*m.SIN_COEFFICIENTS,*m.COS_COEFFICIENTS) for n in coef.pair()],m.SIN_REMAINDER,m.COS_REMAINDER],dtype=np.float64)
 SHADOW=shadow;m._trig_bounds=bounds
@lru_cache(maxsize=8192)
def bounds(lo,hi,cosine):
 t=time.monotonic_ns();out=np.zeros(2,dtype=np.float64);status=LIB.trig_bounds(lo,hi,int(cosine),COEFS,out)
 if status<0:return ORIGINAL(lo,hi,cosine)
 result=tuple(float(x) for x in out)
 if SHADOW:
  expected=ORIGINAL(lo,hi,cosine);assert np.asarray(expected).tobytes()==out.tobytes(),'TRIG_INTERVAL_BYTES_CHANGED'
 ROWS.append(dict(elapsed_ms=(time.monotonic_ns()-t)/1e6,cosine=bool(cosine),shadow=SHADOW));return result
