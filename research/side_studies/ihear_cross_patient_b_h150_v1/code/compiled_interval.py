"""Same outward binary64 operations compiled with the existing GCC toolchain.

No fast math, no contraction, unchanged proof domain, thresholds and record.
Python retains finite/geometry checks and math.fsum. Failed kernel falls back
to the original certificate. Static Taylor coefficients are original values.
"""
from task_bootstrap import *
import ctypes,math,numpy as np
SOURCE=r'''
#include <cmath>
#include <algorithm>
#include <limits>
#include <stdexcept>
static double dn(double x){return std::nextafter(x,-INFINITY);}
static double up(double x){return std::nextafter(x,INFINITY);}
struct I {
 double lo,hi;
 I(double a):lo(a),hi(a){check();}
 I(double a,double b):lo(a),hi(b){check();}
 void check(){if(!(std::isfinite(lo)&&std::isfinite(hi)&&lo<=hi))throw 1;}
 I operator+(I b)const{return I(dn(lo+b.lo),up(hi+b.hi));}
 I operator-()const{return I(-hi,-lo);}
 I operator-(I b)const{return *this+(-b);}
 I operator*(I b)const{double p[]={lo*b.lo,lo*b.hi,hi*b.lo,hi*b.hi};double a=p[0],z=p[0];for(int j=1;j<4;j++){a=std::min(a,p[j]);z=std::max(z,p[j]);}return I(dn(a),up(z));}
 I abs()const{return I(lo<=0.&&0.<=hi?0.:std::min(std::fabs(lo),std::fabs(hi)),std::max(std::fabs(lo),std::fabs(hi)));}
};
static I minimum(I a,I b){return I(std::min(a.lo,b.lo),std::min(a.hi,b.hi));}
static I sqrtn(I a){return I(std::max(0.,dn(std::sqrt(std::max(0.,a.lo)))),up(std::sqrt(std::max(0.,a.hi))));}
static I trig(I x,bool cosine,const double*t){
 if(x.abs().hi>4.)throw 1;
 const double*c=t+(cosine?36:0);I square=x*x;I value(c[34],c[35]);
 for(int j=16;j>=0;j--)value=I(c[2*j],c[2*j+1])+square*value;
 if(!cosine)value=x*value;double rem=t[cosine?73:72];value=value+I(-rem,rem);
 return I(std::max(-1.,value.lo),std::min(1.,value.hi));
}
static void endpoint(const double*v,const double*t,I q0,I q1,I*out){
 I shank=trig(q0-q1,false,t),radial=trig(q0-q1,true,t);
 I knee=I(v[17])+I(v[18])+I(v[14])*trig(q0,false,t);
 I cuff=knee+I(v[15])*shank+I(v[19]);
 out[0]=I(v[20]);
 out[1]=minimum(knee,knee+I(v[16])*shank)-I(v[25])-I(v[26])-I(v[21]);
 I sr=sqrtn(I(1.)-shank*shank);
 out[2]=cuff-I(v[23])*shank.abs()-I(v[24])*sr-I(v[26]);
 out[3]=cuff-I(.5*v[27])*shank.abs()-I(v[28])*sr-I(v[26]);
 out[4]=minimum(cuff+I(v[22])*radial,cuff+I(v[24])*radial)-I(.018)*sqrtn(I(1.)-radial*radial)-I(v[26]);
}
static double hypotup(double a,double b){I square=I(a)*I(a)+I(b)*I(b);return up(std::sqrt(square.hi));}
extern "C" int certificate(const double*v,const double*t,double*out){
 try{
 I q0[]={I(v[0]),I(v[6])},delta[]={I(v[12]),I(v[13])};
 I q1[]={q0[0]+delta[0],q0[1]+delta[1]};
 double canonical[]={0.,0.,0.,10.,-15.,6.};
 I residual[2][6]={{I(0.),I(0.),I(0.),I(0.),I(0.),I(0.)},{I(0.),I(0.),I(0.),I(0.),I(0.),I(0.)}};
 for(int j=0;j<2;j++)for(int k=0;k<6;k++)residual[j][k]=I(v[j*6+k])-(k==0?q0[j]:delta[j]*I(canonical[k]));
 I e1i(0.),ephii(0.);for(int k=0;k<6;k++){e1i=e1i+residual[0][k].abs();ephii=ephii+(residual[0][k]-residual[1][k]).abs();}
 double e1=e1i.hi,ephi=ephii.hi;
 if(std::max(e1,ephi)>1e-10)return 0;
 double lo=std::min(q0[0].lo,q1[0].lo),hi=std::max(q0[0].hi,q1[0].hi);
 if(lo<0.||hi>v[29])return 0;
 if(std::max((q0[0]-q0[1]).abs().hi,(q1[0]-q1[1]).abs().hi)>4.)return 0;
 double coslo=trig(I(hi),true,t).lo,coshi=trig(I(lo),true,t).hi;
 I k=I(v[14])*delta[0]*I(coslo,coshi),dphi=(delta[0]-delta[1]).abs();
 I radii[]={I(v[16]),I(v[15])+I(hypotup(v[23],v[24])),I(v[15])+I(hypotup(.5*v[27],v[28])),I(v[15])+I(v[22])+I(.018)};
 I ends[2][5]={{I(0.),I(0.),I(0.),I(0.),I(0.)},{I(0.),I(0.),I(0.),I(0.),I(0.)}};
 endpoint(v,t,q0[0],q0[1],ends[0]);endpoint(v,t,q1[0],q1[1],ends[1]);
 out[0]=1.;out[1]=e1;out[2]=ephi;out[3]=k.lo;out[4]=k.hi;out[5]=dphi.lo;out[6]=dphi.hi;
 for(int b=0;b<4;b++){
  I rd=radii[b]*dphi;I derivative(k.lo-rd.hi,k.hi+rd.hi);derivative=I(dn(derivative.lo),up(derivative.hi));
  int which=derivative.lo>=0.?0:(derivative.hi<=0.?1:-1);
  I loss=I(v[14])*I(e1)+radii[b]*I(ephi);int a=7+b*8;
  out[a]=derivative.lo;out[a+1]=derivative.hi;out[a+2]=radii[b].hi;out[a+3]=which;out[a+4]=loss.hi;
  if(which>=0){out[a+5]=ends[which][b+1].lo;out[a+6]=ends[which][b+1].hi;out[a+7]=(ends[which][b+1]-loss).lo;}
 }
 out[39]=(I(lo)-I(e1)).lo>=0.&&(I(hi)+I(e1)).hi<=v[29]?1.:0.;return 1;
 }catch(...){return -1;}
}
'''
LIB=None;ORIGINAL=None;ROWS=[];SHADOW=False
def build():
 folder=STUDY/'compiled_interval';folder.mkdir(exist_ok=True);source=folder/'interval.cpp';source.write_text(SOURCE)
 identity=hashlib.sha256(SOURCE.encode()).hexdigest();target=folder/(identity+'.so')
 flags=['-std=c++17','-O2','-shared','-fPIC','-fno-fast-math','-ffp-contract=off','-frounding-math']
 if not target.exists():subprocess.run(['g++',*flags,str(source),'-o',str(target)],check=True,capture_output=True)
 save(folder/'BUILD.json',dict(source_sha256=identity,binary_sha256=sha(target),compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],flags=flags,no_installation=True,physics_attempts=0))
 return target
def install(shadow=False):
 global LIB,ORIGINAL,SHADOW
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as m
 if ORIGINAL is None:ORIGINAL=m.monotonic_certificate
 SHADOW=shadow
 if LIB is None:
  LIB=ctypes.CDLL(str(build()));p=np.ctypeslib.ndpointer(dtype=np.float64,ndim=1,flags='C_CONTIGUOUS');LIB.certificate.argtypes=[p,p,p];LIB.certificate.restype=ctypes.c_int
 m.monotonic_certificate=certificate
def certificate(envelope,coefficients):
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import monotonic_clearance as m
 started=time.monotonic_ns();c=np.asarray(coefficients,dtype=float);g=envelope.geometry;tool=m.STAGE5_GEOMETRY.end_effector_from_cuff
 record=dict(method='outward_interval_common_progress_v2',eligible=False,lowers={},body_proofs={},proof_scope='model reference geometry only; no physical invariance or state-estimation guarantee')
 arrays=(c,g.origin_world_m,g.hip_plane_m,g.plane_x_world,g.plane_z_world,tool.translation,tool.rotation,envelope.cuff_reference_translation_world_m)
 if not all(np.all(np.isfinite(x)) for x in arrays):raise ValueError('nonfinite geometry or polynomial cannot be certified')
 if c.shape!=(2,6):return record
 if not (np.array_equal(g.plane_x_world,[1.,0.,0.]) and np.array_equal(g.plane_z_world,[0.,0.,1.]) and np.array_equal(tool.rotation,[[1.,0.,0.],[0.,0.,-1.],[0.,1.,0.]]) and tool.translation[0]==tool.translation[2]==0. and tool.translation[1]>m.SLEEVE_OUTER_RADIUS_M):return record
 vals=[g.thigh_length_m,g.cuff_distance_m,envelope.shank_length_upper_m]
 if not np.all(np.isfinite(vals)) or min(vals)<=0.:raise ValueError('invalid geometry dimensions')
 v=np.asarray([*c.ravel(),*[float(math.fsum(row)-row[0]) for row in c],g.thigh_length_m,g.cuff_distance_m,envelope.shank_length_upper_m,float(g.origin_world_m[2]),float(g.hip_plane_m[1]),float(envelope.cuff_reference_translation_world_m[2]),envelope.registered_proximal_installation_gap_lower_m,envelope.existing_shank_margin_m,float(tool.translation[1]),m.SLEEVE_HALF_LENGTH_M,m.SLEEVE_OUTER_RADIUS_M,m.SHANK_RADIUS_M,m.BED_HEIGHT_M,m.STAGE5_GEOMETRY.cuff_bar_length_m,m.STAGE5_GEOMETRY.cuff_bar_radius_m,math.pi],dtype=np.float64)
 t=np.asarray([*[n for coef in (*m.SIN_COEFFICIENTS,*m.COS_COEFFICIENTS) for n in coef.pair()],m.SIN_REMAINDER,m.COS_REMAINDER],dtype=np.float64);out=np.zeros(40,dtype=np.float64);status=LIB.certificate(v,t,out)
 if status<0:record=ORIGINAL(envelope,coefficients)
 elif status:
  record.update(eligible=True,coefficient_residual_q1_rad=float(out[1]),coefficient_residual_phi_rad=float(out[2]),knee_derivative_interval=out[3:5].tolist(),delta_phi_abs_interval=out[5:7].tolist())
  for b,name in enumerate(('distal_shank_m','sleeve_m','cuff_bar_m','cuff_adapter_m')):
   a=7+8*b;which=int(out[a+3]);which=None if which<0 else which
   proof=dict(derivative_interval=out[a:a+2].tolist(),radius_upper_m=float(out[a+2]),selected_endpoint=which,residual_loss_upper_m=float(out[a+4]))
   if which is not None:lower=float(out[a+7]);record['lowers'][name]=lower;proof.update(endpoint_interval_m=out[a+5:a+7].tolist(),lower_m=lower)
   record['body_proofs'][name]=proof
  if out[39]:record['lowers']['proximal_thigh_m']=envelope.registered_proximal_installation_gap_lower_m;record['body_proofs']['proximal_thigh_m']=dict(constant_registered_floor=True,lower_m=envelope.registered_proximal_installation_gap_lower_m)
 elapsed=(time.monotonic_ns()-started)/1e6
 if SHADOW:
  expected=ORIGINAL(envelope,coefficients)
  assert expected==record,'COMPILED_INTERVAL_CERTIFICATE_MISMATCH'
  # Byte equality includes signed zeros and every numerical proof value.
  import pickle
  assert pickle.dumps(expected,protocol=5)==pickle.dumps(record,protocol=5),'COMPILED_PROOF_BYTES_MISMATCH'
 ROWS.append(dict(elapsed_ms=elapsed,eligible=record['eligible'],fallback=status<0,shadow=SHADOW))
 return record
