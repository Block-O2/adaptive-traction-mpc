#define PY_SSIZE_T_CLEAN
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
#include <mujoco/mujoco.h>
#include <cstring>
#include <cmath>
static PyObject* matmul=nullptr;
static PyObject* enum_class=nullptr;
// NumPy scalar **2 uses libm pow. Prevent constant-exponent strength reduction.
static double (* volatile scalar_power)(double,double)=std::pow;
struct Context { double k[3],d[3],rest[3],R0[9],kr,dr,last[36]; bool valid=false; PyObject* value=nullptr; PyObject* callback=nullptr; };
static void destroy(PyObject* cap){auto c=(Context*)PyCapsule_GetPointer(cap,"fast.interface.v1");if(c){Py_XDECREF(c->value);Py_XDECREF(c->callback);delete c;}}
static bool array_copy(PyObject* o,double* out,int n){auto a=(PyArrayObject*)PyArray_FROM_OTF(o,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO);if(!a)return false;if(PyArray_SIZE(a)!=n){Py_DECREF(a);PyErr_SetString(PyExc_ValueError,"fixed shape mismatch");return false;}std::memcpy(out,PyArray_DATA(a),n*sizeof(double));Py_DECREF(a);return true;}
static PyObject* array(const double* x,int n){npy_intp dims[]={n};auto a=PyArray_SimpleNew(1,dims,NPY_DOUBLE);if(a)std::memcpy(PyArray_DATA((PyArrayObject*)a),x,n*sizeof(double));return a;}
static double dot(const double* a,const double* b,int n){npy_intp dims[]={n};auto x=PyArray_SimpleNewFromData(1,dims,NPY_DOUBLE,(void*)a);auto y=PyArray_SimpleNewFromData(1,dims,NPY_DOUBLE,(void*)b);auto out=PyObject_CallFunctionObjArgs(matmul,x,y,nullptr);Py_DECREF(x);Py_DECREF(y);if(!out)return NAN;double result=PyFloat_AsDouble(out);Py_DECREF(out);return result;}
static void cross(const double* a,const double* b,double* o){o[0]=a[1]*b[2]-a[2]*b[1];o[1]=a[2]*b[0]-a[0]*b[2];o[2]=a[0]*b[1]-a[1]*b[0];}
static PyObject* cross_vector(PyObject*,PyObject* args){PyObject *a,*b;if(!PyArg_ParseTuple(args,"OO",&a,&b))return nullptr;double x[3],y[3],out[3];if(!array_copy(a,x,3)||!array_copy(b,y,3))return nullptr;cross(x,y,out);return array(out,3);}
// N4: unchanged two-joint soft-limit arithmetic and original qfrc reset.
// p = qmin[2], qmax[2], margin, tolerance, boundary torque, damping.
static void soft_limit_value(const double* q,const double* dq,const double* p,double* torque){
 for(int i=0;i<2;i++){
  double lower=(p[i]+p[4])-p[5],upper=(p[i+2]-p[4])+p[5];torque[i]=0.;
  if(q[i]<lower){double z=(lower-q[i])/p[4];torque[i]=p[6]*scalar_power(z,3.);torque[i]+=(p[7]*scalar_power(z,2.))*((-dq[i]<0.)?0.:-dq[i]);}
  else if(q[i]>upper){double z=(q[i]-upper)/p[4];torque[i]=(-p[6])*scalar_power(z,3.);torque[i]-=(p[7]*scalar_power(z,2.))*((dq[i]<0.)?0.:dq[i]);}
 }
}
static PyObject* soft_limit_arrays(PyObject*,PyObject* args){PyObject *q,*dq,*params;if(!PyArg_ParseTuple(args,"OOO",&q,&dq,&params))return nullptr;double x[2],v[2],p[8],out[2];if(!array_copy(q,x,2)||!array_copy(dq,v,2)||!array_copy(params,p,8))return nullptr;soft_limit_value(x,v,p,out);return array(out,2);}
static PyObject* apply_soft_limits(PyObject*,PyObject* args){
 unsigned long long ma,da;int q0,q1,v0,v1;PyObject* params;
 if(!PyArg_ParseTuple(args,"KKiiiiO",&ma,&da,&q0,&q1,&v0,&v1,&params))return nullptr;
 auto m=(mjModel*)(uintptr_t)ma;auto d=(mjData*)(uintptr_t)da;double p[8],out[2];
 if(!m||!d||q0<0||q1<0||q0>=m->nq||q1>=m->nq||v0<0||v1<0||v0>=m->nv||v1>=m->nv){PyErr_SetString(PyExc_ValueError,"invalid owned soft-limit indices");return nullptr;}
 if(!array_copy(params,p,8))return nullptr;
 double q[]={d->qpos[q0],d->qpos[q1]},v[]={d->qvel[v0],d->qvel[v1]};soft_limit_value(q,v,p,out);
 for(int i=0;i<m->nv;i++){d->qfrc_applied[i]=0.;}d->qfrc_applied[v0]=out[0];d->qfrc_applied[v1]=out[1];Py_RETURN_NONE;
}
static void mv(const double* m,const double* x,double* o,bool transpose=false){npy_intp md[]={3,3},vd[]={3};auto matrix=(PyArrayObject*)PyArray_SimpleNewFromData(2,md,NPY_DOUBLE,(void*)m);auto vector=PyArray_SimpleNewFromData(1,vd,NPY_DOUBLE,(void*)x);PyObject* left=transpose?PyArray_Transpose(matrix,nullptr):(PyObject*)matrix;if(!transpose)Py_INCREF(left);auto out=PyObject_CallFunctionObjArgs(matmul,left,vector,nullptr);Py_DECREF(left);Py_DECREF(matrix);Py_DECREF(vector);if(out){std::memcpy(o,PyArray_DATA((PyArrayObject*)out),3*sizeof(double));Py_DECREF(out);}}
static void matrix_product(const double* a,const double* b,double* out,bool ta,bool tb){npy_intp dims[]={3,3};auto x=(PyArrayObject*)PyArray_SimpleNewFromData(2,dims,NPY_DOUBLE,(void*)a);auto y=(PyArrayObject*)PyArray_SimpleNewFromData(2,dims,NPY_DOUBLE,(void*)b);auto left=ta?PyArray_Transpose(x,nullptr):(PyObject*)x;auto right=tb?PyArray_Transpose(y,nullptr):(PyObject*)y;if(!ta)Py_INCREF(left);if(!tb)Py_INCREF(right);auto r=PyObject_CallFunctionObjArgs(matmul,left,right,nullptr);Py_DECREF(left);Py_DECREF(right);Py_DECREF(x);Py_DECREF(y);if(r){std::memcpy(out,PyArray_DATA((PyArrayObject*)r),9*sizeof(double));Py_DECREF(r);}}
// N3: the installed SciPy 1.15.3 Markley/quaternion/rotvec arithmetic.
// A conservative orthogonality interior uses the same arithmetic; matrices
// outside it retain SciPy's complete determinant/SVD/error behavior.
// Reference: https://github.com/scipy/scipy/blob/v1.15.3/scipy/spatial/transform/_rotation.pyx
static bool rotation_interior(const double* R){
 for(int i=0;i<3;i++)for(int j=0;j<3;j++){double v=0.;for(int n=0;n<3;n++)v+=R[i*3+n]*R[j*3+n];if(!std::isfinite(v)||std::abs(v-(i==j?1.:0.))>1e-14)return false;}
 double det=R[0]*(R[4]*R[8]-R[5]*R[7])-R[1]*(R[3]*R[8]-R[5]*R[6])+R[2]*(R[3]*R[7]-R[4]*R[6]);return det>.99;
}
static PyObject* rotation_vector(PyObject*,PyObject* args){
 PyObject *matrix,*fallback;if(!PyArg_ParseTuple(args,"OO",&matrix,&fallback))return nullptr;double R[9];if(!array_copy(matrix,R,9))return nullptr;
 if(!rotation_interior(R))return PyObject_CallOneArg(fallback,matrix);
 double decisions[]={R[0],R[4],R[8],(R[0]+R[4])+R[8]},q[4];int choice=0;for(int i=1;i<4;i++)if(decisions[i]>decisions[choice])choice=i;
 if(choice==3){q[0]=R[7]-R[5];q[1]=R[2]-R[6];q[2]=R[3]-R[1];q[3]=1.+decisions[3];}
 else{int i=choice,j=(i+1)%3,k=(j+1)%3;q[i]=(1.-decisions[3])+2.*R[i*3+i];q[j]=R[j*3+i]+R[i*3+j];q[k]=R[k*3+i]+R[i*3+k];q[3]=R[k*3+j]-R[j*3+k];}
 double norm=std::sqrt(((q[0]*q[0]+q[1]*q[1])+q[2]*q[2])+q[3]*q[3]);for(int i=0;i<4;i++)q[i]/=norm;
 if(q[3]<0.||(q[3]==0.&&(q[0]<0.||(q[0]==0.&&(q[1]<0.||(q[1]==0.&&q[2]<0.))))))for(int i=0;i<4;i++)q[i]*=-1.;
 double vectornorm=std::sqrt((q[0]*q[0]+q[1]*q[1])+q[2]*q[2]);double angle=2.*std::atan2(vectornorm,q[3]),scale;
 if(angle<=1e-3){double a2=angle*angle;scale=(2.+a2/12.)+((7.*a2)*a2)/2880.;}else scale=angle/std::sin(angle/2.);
 double v[]={scale*q[0],scale*q[1],scale*q[2]};return array(v,3);
}
static PyObject* create(PyObject*,PyObject* args){PyObject *k,*d,*r,*R;double kr,dr;if(!PyArg_ParseTuple(args,"OOOOdd",&k,&d,&r,&R,&kr,&dr))return nullptr;auto c=new Context;if(!array_copy(k,c->k,3)||!array_copy(d,c->d,3)||!array_copy(r,c->rest,3)||!array_copy(R,c->R0,9)){delete c;return nullptr;}c->kr=kr;c->dr=dr;return PyCapsule_New(c,"fast.interface.v1",destroy);}
// State order per site: position[3], rotation[9], world angular[3], world linear[3].
static PyObject* evaluate(Context* c,const double* state,PyObject* rotvec){
 if(c->valid&&c->callback==rotvec&&std::memcmp(c->last,state,36*sizeof(double))==0){Py_INCREF(c->value);return c->value;}
 auto rp=state;auto rr=state+3;auto rw=state+12;auto rv=state+15;auto hp=state+18;auto rh=state+21;auto hw=state+30;auto hv=state+33;
 double r[3],x[3],u[3],omega[3],temp[3],wxr[3],A[9],B[9];for(int i=0;i<3;i++)r[i]=rp[i]-hp[i];mv(rh,r,x,true);for(int i=0;i<3;i++)x[i]-=c->rest[i];cross(hw,r,wxr);for(int i=0;i<3;i++)temp[i]=(rv[i]-hv[i])-wxr[i];mv(rh,temp,u,true);for(int i=0;i<3;i++)temp[i]=rw[i]-hw[i];mv(rh,temp,omega,true);
 matrix_product(rh,rr,A,true,false);matrix_product(A,c->R0,B,false,true);
 npy_intp dims[]={3,3};auto matrix=PyArray_SimpleNew(2,dims,NPY_DOUBLE);if(!matrix)return nullptr;std::memcpy(PyArray_DATA((PyArrayObject*)matrix),B,sizeof(B));auto theta_object=PyObject_CallOneArg(rotvec,matrix);Py_DECREF(matrix);if(!theta_object)return nullptr;double theta[3];if(!array_copy(theta_object,theta,3)){Py_DECREF(theta_object);return nullptr;}Py_DECREF(theta_object);
 double force[3],couple[3],transport[3],human[6],robot[6],hvel[6],rvel[6],kx[3],du[3],ku[3];
 for(int i=0;i<3;i++){temp[i]=c->k[i]*x[i]+c->d[i]*u[i];kx[i]=c->k[i]*x[i];du[i]=c->d[i]*u[i];ku[i]=c->k[i]*u[i];}mv(rh,temp,force);
 for(int i=0;i<3;i++)temp[i]=c->kr*theta[i]+c->dr*omega[i];mv(rh,temp,couple);cross(r,force,transport);
 for(int i=0;i<3;i++){human[i]=force[i];human[i+3]=couple[i]+transport[i];robot[i]=-force[i];robot[i+3]=-couple[i];hvel[i]=hv[i];hvel[i+3]=hw[i];rvel[i]=rv[i];rvel[i+3]=rw[i];}
 auto result=PyTuple_New(10);if(!result)return nullptr;double* vectors[]={x,u,theta,omega,human,robot};int sizes[]={3,3,3,3,6,6};for(int i=0;i<6;i++){auto a=array(vectors[i],sizes[i]);if(!a){Py_DECREF(result);return nullptr;}PyTuple_SET_ITEM(result,i,a);}
 double scalars[]={.5*(dot(x,kx,3)+c->kr*dot(theta,theta,3)),dot(u,du,3)+c->dr*dot(omega,omega,3),dot(human,hvel,6)+dot(robot,rvel,6),dot(x,ku,3)+c->kr*dot(theta,omega,3)};
 for(int i=0;i<4;i++){PyTuple_SET_ITEM(result,i+6,PyFloat_FromDouble(scalars[i]));}
 if(PyErr_Occurred()){Py_DECREF(result);return nullptr;}
 Py_XDECREF(c->value);c->value=result;Py_INCREF(result);Py_XDECREF(c->callback);c->callback=rotvec;Py_INCREF(rotvec);std::memcpy(c->last,state,36*sizeof(double));c->valid=true;return result;
}
static PyObject* evaluate_arrays(PyObject*,PyObject* args){PyObject *cap,*a,*rotvec;if(!PyArg_ParseTuple(args,"OOO",&cap,&a,&rotvec))return nullptr;auto c=(Context*)PyCapsule_GetPointer(cap,"fast.interface.v1");if(!c)return nullptr;double state[36];if(!array_copy(a,state,36))return nullptr;return evaluate(c,state,rotvec);}
static PyObject* evaluate_data(PyObject*,PyObject* args){PyObject *cap,*rotvec;unsigned long long ma,da;int rs,hs;if(!PyArg_ParseTuple(args,"OKKiiO",&cap,&ma,&da,&rs,&hs,&rotvec))return nullptr;auto c=(Context*)PyCapsule_GetPointer(cap,"fast.interface.v1");if(!c)return nullptr;auto m=(mjModel*)(uintptr_t)ma;auto d=(mjData*)(uintptr_t)da;if(!m||!d||rs<0||hs<0||rs>=m->nsite||hs>=m->nsite){PyErr_SetString(PyExc_ValueError,"invalid owned MuJoCo state");return nullptr;}double state[36];int sites[]={rs,hs};for(int i=0;i<2;i++){double* o=state+i*18;std::memcpy(o,d->site_xpos+sites[i]*3,3*sizeof(double));std::memcpy(o+3,d->site_xmat+sites[i]*9,9*sizeof(double));mj_objectVelocity(m,d,mjOBJ_SITE,sites[i],o+12,0);}return evaluate(c,state,rotvec);}
static PyObject* apply_wrenches(PyObject*,PyObject* args){unsigned long long ma,da;int rs,hs;PyObject *human,*robot,*force;if(!PyArg_ParseTuple(args,"KKiiOOO",&ma,&da,&rs,&hs,&human,&robot,&force))return nullptr;auto m=(mjModel*)(uintptr_t)ma;auto d=(mjData*)(uintptr_t)da;auto h=(PyArrayObject*)PyArray_FROM_OTF(human,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO);auto r=(PyArrayObject*)PyArray_FROM_OTF(robot,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO);auto f=(PyArrayObject*)PyArray_FROM_OTF(force,NPY_DOUBLE,NPY_ARRAY_CARRAY);if(!h||!r||!f){Py_XDECREF(h);Py_XDECREF(r);Py_XDECREF(f);return nullptr;}if(PyArray_SIZE(h)!=6||PyArray_SIZE(r)!=6||PyArray_SIZE(f)!=m->nv||rs<0||hs<0||rs>=m->nsite||hs>=m->nsite){Py_DECREF(h);Py_DECREF(r);Py_DECREF(f);PyErr_SetString(PyExc_ValueError,"invalid wrench shape/site");return nullptr;}auto hp=(double*)PyArray_DATA(h);auto rp=(double*)PyArray_DATA(r);auto fp=(double*)PyArray_DATA(f);for(int i=0;i<m->nv;i++)fp[i]=0.;mj_applyFT(m,d,hp,hp+3,d->site_xpos+hs*3,m->site_bodyid[hs],fp);mj_applyFT(m,d,rp,rp+3,d->site_xpos+rs*3,m->site_bodyid[rs],fp);for(int i=0;i<m->nv;i++)d->qfrc_applied[i]+=fp[i];Py_DECREF(h);Py_DECREF(r);Py_DECREF(f);Py_RETURN_NONE;}
// N5: fixed four-state feature map, in the original elementwise order.
static PyObject* state_features4(PyObject*,PyObject* args){
 PyObject *state,*lower,*upper;double velocity;
 if(!PyArg_ParseTuple(args,"OOOd",&state,&lower,&upper,&velocity))return nullptr;
 double x[4],l[2],u[2],out[5];
 if(!array_copy(state,x,4)||!array_copy(lower,l,2)||!array_copy(upper,u,2))return nullptr;
 for(int i=0;i<4;i++)if(!std::isfinite(x[i])){PyErr_SetString(PyExc_ValueError,"state must contain finite [q1, q2, dq1, dq2]");return nullptr;}
 out[0]=1.;for(int i=0;i<2;i++){out[i+1]=((2.*(x[i]-l[i]))/(u[i]-l[i]))-1.;out[i+3]=x[i+2]/(velocity+std::abs(x[i+2]));}
 return array(out,5);
}
// The exact original Gram product uses NumPy matmul. The original NumPy
// determinant is retained; only fixed-shape isclose/reduction dispatch moves.
static PyObject* validate_rigid(PyObject*,PyObject* args){
 PyObject *rotation,*determinant;if(!PyArg_ParseTuple(args,"OO",&rotation,&determinant))return nullptr;
 auto r=(PyArrayObject*)PyArray_FROM_O(rotation);if(!r)return nullptr;
 auto transposed=PyArray_Transpose(r,nullptr);if(!transposed){Py_DECREF(r);return nullptr;}
 auto product=PyObject_CallFunctionObjArgs(matmul,transposed,r,nullptr);Py_DECREF(transposed);Py_DECREF(r);if(!product)return nullptr;
 double gram[9];bool copied=array_copy(product,gram,9);Py_DECREF(product);if(!copied)return nullptr;
 for(int i=0;i<9;i++){double identity=(i%4==0)?1.:0.;double difference=std::abs(gram[i]-identity);double tolerance=1e-12+1e-5*std::abs(identity);
  if(!(difference<=tolerance)){PyErr_SetString(PyExc_ValueError,"rotation must be orthonormal");return nullptr;}}
 auto det=PyObject_CallOneArg(determinant,rotation);if(!det)return nullptr;double value=PyFloat_AsDouble(det);Py_DECREF(det);if(PyErr_Occurred())return nullptr;
 if(value<0.){PyErr_SetString(PyExc_ValueError,"rotation must be right-handed");return nullptr;}Py_RETURN_NONE;
}
// N6: NumPy supplies the exact sin/cos arrays and all geometric dot/norm
// constants. Elementwise operations keep the original order without dispatch.
static double gap(double a,double b,double axis,double radius,double bed){double v=1.-axis*axis;double radial=radius*std::sqrt(v>=0.?v:0.);return ((a<b)?a:b)-radial-bed;}
static PyObject* table_margins(PyObject*,PyObject* args){
 PyObject *angles,*trigs,*params;if(!PyArg_ParseTuple(args,"OOO",&angles,&trigs,&params))return nullptr;
 auto q=(PyArrayObject*)PyArray_FROM_OTF(angles,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO);auto trig=(PyArrayObject*)PyArray_FROM_OTF(trigs,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO);double p[22];
 if(!q||!trig||!array_copy(params,p,22)){Py_XDECREF(q);Py_XDECREF(trig);return nullptr;}
 if(PyArray_NDIM(q)!=2||PyArray_DIM(q,1)!=2||PyArray_NDIM(trig)!=2||PyArray_DIM(trig,0)!=4||PyArray_DIM(trig,1)!=PyArray_DIM(q,0)){Py_DECREF(q);Py_DECREF(trig);PyErr_SetString(PyExc_ValueError,"invalid margin array shapes");return nullptr;}
 npy_intp n=PyArray_DIM(q,0),dims[]={5,n};auto out=(PyArrayObject*)PyArray_SimpleNew(2,dims,NPY_DOUBLE);if(!out){Py_DECREF(q);Py_DECREF(trig);return nullptr;}
 auto x=(double*)PyArray_DATA(q);auto t=(double*)PyArray_DATA(trig);auto y=(double*)PyArray_DATA(out);
 bool structural=std::abs(p[0])<1e-9&&p[1]>0.;for(npy_intp i=0;i<n;i++)if(!(x[2*i]>=0.&&x[2*i]<=p[21]))structural=false;
 for(npy_intp i=0;i<n;i++){
  double thigh=t[i]*p[0]+t[n+i]*p[1],shank=t[2*n+i]*p[0]+t[3*n+i]*p[1];
  double knee=p[2]+p[3]*thigh,ankle=knee+p[4]*shank,cuff=(knee+p[5]*shank)+p[6];
  double sa=cuff-p[7]*shank,sb=cuff+p[7]*shank,ba=cuff-p[8]*shank,bb=cuff+p[8]*shank;
  y[i]=structural?p[9]:((p[2]<knee)?p[2]:knee)-p[10]-p[11];
  y[n+i]=(((knee<ankle)?knee:ankle)-p[12]-p[11])-p[13];
  y[2*n+i]=gap(sa,sb,shank,p[14],p[11]);y[3*n+i]=gap(ba,bb,shank,p[15],p[11]);
  if(p[16]>0.){double frame_z=(-t[3*n+i])*p[0]+t[2*n+i]*p[1];double offset=(shank*p[17]+p[18])+frame_z*p[19];
   double flange=cuff-offset,connector=flange+(p[16]/p[20])*offset,axis=offset/p[20];y[4*n+i]=gap(flange,connector,axis,.018,p[11]);
  }else y[4*n+i]=(cuff-.018)-p[11];
 }
 Py_DECREF(q);Py_DECREF(trig);return (PyObject*)out;
}
static PyObject* planar_jacobian(PyObject*,PyObject* args){
 PyObject *q,*px,*pz;double thigh,distance;if(!PyArg_ParseTuple(args,"OOOdd",&q,&px,&pz,&thigh,&distance))return nullptr;
 double x[2],a[3],b[3];if(!array_copy(q,x,2)||!array_copy(px,a,3)||!array_copy(pz,b,3))return nullptr;
 double phi=x[0]-x[1],s1=std::sin(x[0]),c1=std::cos(x[0]),sp=std::sin(phi),cp=std::cos(phi);npy_intp dims[]={3,2};auto out=(PyArrayObject*)PyArray_SimpleNew(2,dims,NPY_DOUBLE);if(!out)return nullptr;auto y=(double*)PyArray_DATA(out);
 for(int i=0;i<3;i++){double first=(-s1)*a[i]+c1*b[i],shank=(-sp)*a[i]+cp*b[i];y[2*i]=thigh*first+distance*shank;y[2*i+1]=(-distance)*shank;}return (PyObject*)out;
}
static PyObject* regressor2(PyObject*,PyObject* args){
 PyObject *q,*v,*accel;if(!PyArg_ParseTuple(args,"OOO",&q,&v,&accel))return nullptr;double x[2],dq[2],ddq[2];if(!array_copy(q,x,2)||!array_copy(v,dq,2)||!array_copy(accel,ddq,2))return nullptr;
 npy_intp dims[]={2,11};auto out=(PyArrayObject*)PyArray_ZEROS(2,dims,NPY_DOUBLE,0);if(!out)return nullptr;auto y=(double*)PyArray_DATA(out);double cosine=std::cos(x[1]),sine=std::sin(x[1]),phi=x[0]-x[1];
 y[0]=ddq[0];y[1]=-ddq[1];y[2]=((2.*cosine)*ddq[0]-cosine*ddq[1])+sine*(((-2.*dq[0])*dq[1])+scalar_power(dq[1],2.));y[3]=std::cos(x[0]);y[4]=std::cos(phi);y[5]=x[0];y[7]=-1.;y[9]=dq[0];
 y[12]=-ddq[0]+ddq[1];y[13]=(-cosine)*ddq[0]+sine*scalar_power(dq[0],2.);y[15]=-std::cos(phi);y[17]=x[1];y[19]=-1.;y[21]=dq[1];return (PyObject*)out;
}
// N7: original fixed-point inversion, retaining SciPy rotations and NumPy
// matrix products. Only fixed-size vector expressions/dispatch move to C++.
static PyObject* observer_invert(PyObject*,PyObject* args){
 PyObject *measurement,*params,*previous,*rotcb;double dt;int iterations,initial;
 if(!PyArg_ParseTuple(args,"OOOdipO",&measurement,&params,&previous,&dt,&iterations,&initial,&rotcb))return nullptr;
 double m[24],p[14],prior[6];if(!array_copy(measurement,m,24)||!array_copy(params,p,14)||!array_copy(previous,prior,6))return nullptr;
 if(iterations<1||(!initial&&dt<=0.)){PyErr_SetString(PyExc_ValueError,"interface observer requires increasing sample timestamps");return nullptr;}
 double x[3],theta[3],velocity[3]={0.,0.,0.},angular[3]={0.,0.,0.},relative[9],humanR[9],forceH[3],coupleH[3],r[3],temp[3],couple[3],transport[3];
 for(int i=0;i<3;i++){x[i]=prior[i];theta[i]=prior[i+3];}
 auto rotation=[&]()->bool{
  for(int i=0;i<3;i++)temp[i]=theta[i]+p[i+9];auto vector=array(temp,3);if(!vector)return false;auto out=PyObject_CallOneArg(rotcb,vector);Py_DECREF(vector);if(!out)return false;bool good=array_copy(out,relative,9);Py_DECREF(out);if(!good)return false;
  matrix_product(m+9,relative,humanR,false,true);return !PyErr_Occurred();};
 for(int repeat=0;repeat<iterations;repeat++){
  if(!rotation())return nullptr;mv(humanR,m,forceH,true);
  for(int i=0;i<3;i++){
   if(initial){x[i]=p[i+6]+forceH[i]/p[i];velocity[i]=0.;}
   else{x[i]=((forceH[i]+(p[i+3]*prior[i])/dt)+p[i]*p[i+6])/(p[i]+p[i+3]/dt);velocity[i]=(x[i]-prior[i])/dt;}
   temp[i]=x[i]+p[i+6];
  }
  mv(humanR,temp,r);cross(r,m,transport);for(int i=0;i<3;i++)couple[i]=m[i+3]-transport[i];mv(humanR,couple,coupleH,true);
  for(int i=0;i<3;i++){
   if(initial){theta[i]=p[i+9]+coupleH[i]/p[12];angular[i]=0.;}
   else{theta[i]=((coupleH[i]+(p[13]*prior[i+3])/dt)+p[12]*p[i+9])/(p[12]+p[13]/dt);angular[i]=(theta[i]-prior[i+3])/dt;}
  }
 }
 if(!rotation())return nullptr;for(int i=0;i<3;i++)temp[i]=x[i]+p[i+6];mv(humanR,temp,r);
 double humanOmega[3],humanVelocity[3],position[3],rotated[3];mv(humanR,angular,rotated);for(int i=0;i<3;i++)humanOmega[i]=m[i+21]-rotated[i];cross(humanOmega,r,transport);mv(humanR,velocity,rotated);
 for(int i=0;i<3;i++){humanVelocity[i]=(m[i+18]-transport[i])-rotated[i];position[i]=m[i+6]-r[i];}
 if(PyErr_Occurred())return nullptr;auto result=PyTuple_New(10);if(!result)return nullptr;double* vectors[]={x,velocity,theta,angular,position,humanR,humanVelocity,humanOmega,m,m+3};
 for(int i=0;i<10;i++){if(i==5){npy_intp dims[]={3,3};auto out=PyArray_SimpleNew(2,dims,NPY_DOUBLE);if(!out){Py_DECREF(result);return nullptr;}std::memcpy(PyArray_DATA((PyArrayObject*)out),humanR,9*sizeof(double));PyTuple_SET_ITEM(result,i,out);}else{auto out=array(vectors[i],3);if(!out){Py_DECREF(result);return nullptr;}PyTuple_SET_ITEM(result,i,out);}}
 return result;
}
// N8: exact original complete raw-value tree. No hashes/dependencies dropped.
// Unsupported subclasses retain their Python property/iteration behavior.
static PyObject* raw_tree_inner(PyObject*,PyObject*);
static PyObject* raw_tree_value(PyObject* value,PyObject* fallback){
 auto type=(PyObject*)Py_TYPE(value);
 if(PyArray_CheckExact(value)){
  auto a=(PyArrayObject*)value;auto dtype=PyObject_GetAttrString(value,"dtype");if(!dtype)return nullptr;auto str=PyObject_GetAttrString(dtype,"str");Py_DECREF(dtype);auto shape=PyObject_GetAttrString(value,"shape");auto bytes=PyArray_ToString(a,NPY_CORDER);
  if(!str||!shape||!bytes){Py_XDECREF(str);Py_XDECREF(shape);Py_XDECREF(bytes);return nullptr;}auto out=PyTuple_Pack(4,(PyObject*)&PyArray_Type,str,shape,bytes);Py_DECREF(str);Py_DECREF(shape);Py_DECREF(bytes);return out;
 }
 if(PyArray_Check(value))return PyObject_CallOneArg(fallback,value);
 int is_enum=PyObject_IsInstance(value,enum_class);if(is_enum<0)return nullptr;
 if(is_enum){auto field=PyObject_GetAttrString(value,"value");if(!field)return nullptr;auto raw=raw_tree_inner(field,fallback);Py_DECREF(field);if(!raw)return nullptr;auto out=PyTuple_Pack(2,type,raw);Py_DECREF(raw);return out;}
 if(PyType_Check(value))return PyTuple_Pack(2,(PyObject*)&PyType_Type,value);
 if(PyFloat_Check(value)){double number=PyFloat_AsDouble(value);if(PyErr_Occurred())return nullptr;auto bytes=PyBytes_FromStringAndSize((const char*)&number,sizeof(double));if(!bytes)return nullptr;auto out=PyTuple_Pack(2,type,bytes);Py_DECREF(bytes);return out;}
 if(value==Py_None||PyUnicode_Check(value)||PyBytes_Check(value)||PyLong_Check(value))return PyTuple_Pack(2,type,value);
 if(PyList_CheckExact(value)||PyTuple_CheckExact(value)){
  Py_ssize_t count=PySequence_Size(value);auto items=PyTuple_New(count);if(!items)return nullptr;
  for(Py_ssize_t i=0;i<count;i++){auto item=PyList_CheckExact(value)?PyList_GET_ITEM(value,i):PyTuple_GET_ITEM(value,i);auto raw=raw_tree_inner(item,fallback);if(!raw){Py_DECREF(items);return nullptr;}PyTuple_SET_ITEM(items,i,raw);}
  auto out=PyTuple_Pack(2,type,items);Py_DECREF(items);return out;
 }
 if(PyDict_CheckExact(value)){
  auto items=PyTuple_New(PyDict_Size(value));if(!items)return nullptr;Py_ssize_t position=0,index=0;PyObject *key,*item;
  while(PyDict_Next(value,&position,&key,&item)){auto raw=raw_tree_inner(item,fallback);if(!raw){Py_DECREF(items);return nullptr;}auto pair=PyTuple_Pack(2,key,raw);Py_DECREF(raw);if(!pair){Py_DECREF(items);return nullptr;}PyTuple_SET_ITEM(items,index++,pair);}
  auto out=PyTuple_Pack(2,(PyObject*)&PyDict_Type,items);Py_DECREF(items);return out;
 }
 if(PyList_Check(value)||PyTuple_Check(value)||PyDict_Check(value))return PyObject_CallOneArg(fallback,value);
 auto fields=PyObject_GetAttrString(value,"__dict__");
 if(fields){auto raw=raw_tree_inner(fields,fallback);Py_DECREF(fields);if(!raw)return nullptr;auto out=PyTuple_Pack(2,type,raw);Py_DECREF(raw);return out;}
 if(!PyErr_ExceptionMatches(PyExc_AttributeError))return nullptr;PyErr_Clear();return PyObject_CallOneArg(fallback,value);
}
static PyObject* raw_tree_inner(PyObject* value,PyObject* fallback){if(Py_EnterRecursiveCall(" in exact complete raw tree"))return nullptr;auto out=raw_tree_value(value,fallback);Py_LeaveRecursiveCall();return out;}
static PyObject* raw_value_tree(PyObject*,PyObject* args){PyObject *value,*fallback;if(!PyArg_ParseTuple(args,"OO",&value,&fallback))return nullptr;return raw_tree_inner(value,fallback);}
// N9: powers follow Python float pow (libm), original NumPy 2x6 matmul
// remains authoritative. Returned vectors preserve original finite checks.
static PyObject* quintic_sample(PyObject*,PyObject* args){
 PyObject *coefficients;double elapsed,duration;if(!PyArg_ParseTuple(args,"Odd",&coefficients,&elapsed,&duration))return nullptr;
 if(!std::isfinite(elapsed)||elapsed<0.){PyErr_SetString(PyExc_ValueError,"elapsed_s must be finite and nonnegative");return nullptr;}
 double time=(duration<elapsed)?duration:elapsed,s=time/duration;
 double powers[6]={1.,s,scalar_power(s,2.),scalar_power(s,3.),scalar_power(s,4.),scalar_power(s,5.)};
 double velocity[6]={0.,1.,2.*s,3.*scalar_power(s,2.),4.*scalar_power(s,3.),5.*scalar_power(s,4.)};
 double acceleration[6]={0.,0.,2.,6.*s,12.*scalar_power(s,2.),20.*scalar_power(s,3.)};
 double* vectors[]={powers,velocity,acceleration};double scales[]={1.,duration,scalar_power(duration,2.)};const char* names[]={"q_rad must be a finite two-vector","dq_rad_s must be a finite two-vector","ddq_rad_s2 must be a finite two-vector"};
 auto result=PyTuple_New(3);if(!result)return nullptr;
 for(int i=0;i<3;i++){
  auto input=array(vectors[i],6);if(!input){Py_DECREF(result);return nullptr;}auto out=PyObject_CallFunctionObjArgs(matmul,coefficients,input,nullptr);Py_DECREF(input);if(!out){Py_DECREF(result);return nullptr;}
  double x[2];if(!array_copy(out,x,2)){Py_DECREF(out);Py_DECREF(result);return nullptr;}Py_DECREF(out);
  if(i>0)for(int j=0;j<2;j++)x[j]/=scales[i];
  if(!std::isfinite(x[0])||!std::isfinite(x[1])){Py_DECREF(result);PyErr_SetString(PyExc_ValueError,names[i]);return nullptr;}
  auto value=array(x,2);if(!value){Py_DECREF(result);return nullptr;}PyTuple_SET_ITEM(result,i,value);
 }
 return result;
}
// N11: exactly ONE original step/refresh sequence. Python WallPhysicsSession
// still performs its original sensor, safety and command-owner events per step.
static PyObject* step_interface(Context* c,mjModel* m,mjData* d,int rs,int hs,PyObject* cb,double* force){
 double state[36];int sites[]={rs,hs};
 for(int i=0;i<2;i++){double* o=state+i*18;std::memcpy(o,d->site_xpos+sites[i]*3,3*sizeof(double));std::memcpy(o+3,d->site_xmat+sites[i]*9,9*sizeof(double));mj_objectVelocity(m,d,mjOBJ_SITE,sites[i],o+12,0);}
 auto row=evaluate(c,state,cb);if(!row)return nullptr;
 auto human=(double*)PyArray_DATA((PyArrayObject*)PyTuple_GET_ITEM(row,4));auto robot=(double*)PyArray_DATA((PyArrayObject*)PyTuple_GET_ITEM(row,5));
 for(int i=0;i<m->nv;i++)force[i]=0.;
 mj_applyFT(m,d,human,human+3,d->site_xpos+hs*3,m->site_bodyid[hs],force);
 mj_applyFT(m,d,robot,robot+3,d->site_xpos+rs*3,m->site_bodyid[rs],force);
 for(int i=0;i<m->nv;i++)d->qfrc_applied[i]+=force[i];return row;
}
static void step_soft(mjModel* m,mjData* d,int q0,int q1,int v0,int v1,const double* p){
 double q[]={d->qpos[q0],d->qpos[q1]},v[]={d->qvel[v0],d->qvel[v1]},out[2];soft_limit_value(q,v,p,out);
 for(int i=0;i<m->nv;i++)d->qfrc_applied[i]=0.;d->qfrc_applied[v0]=out[0];d->qfrc_applied[v1]=out[1];
}
static PyObject* plant_single_step(PyObject*,PyObject* args){
 PyObject *cap,*cb,*params,*forces;unsigned long long ma,da;int rs,hs,weld,q0,q1,v0,v1;
 if(!PyArg_ParseTuple(args,"OKKiiiiiiiOOO",&cap,&ma,&da,&rs,&hs,&weld,&q0,&q1,&v0,&v1,&params,&cb,&forces))return nullptr;
 auto c=(Context*)PyCapsule_GetPointer(cap,"fast.interface.v1");if(!c)return nullptr;auto m=(mjModel*)(uintptr_t)ma;auto d=(mjData*)(uintptr_t)da;
 if(!m||!d||rs<0||hs<0||rs>=m->nsite||hs>=m->nsite||weld<0||weld>=m->neq||q0<0||q1<0||q0>=m->nq||q1>=m->nq||v0<0||v1<0||v0>=m->nv||v1>=m->nv){PyErr_SetString(PyExc_ValueError,"invalid owned single-step indices");return nullptr;}
 double p[8];if(!array_copy(params,p,8))return nullptr;
 if(!PyArray_Check(forces)||PyArray_TYPE((PyArrayObject*)forces)!=NPY_DOUBLE||!PyArray_ISCARRAY((PyArrayObject*)forces)||PyArray_SIZE((PyArrayObject*)forces)!=m->nv){PyErr_SetString(PyExc_ValueError,"single-step force buffer must be owned writable contiguous float64");return nullptr;}
 auto force=(double*)PyArray_DATA((PyArrayObject*)forces);
 d->eq_active[weld]=0;mj_step1(m,d);step_soft(m,d,q0,q1,v0,v1,p);
 auto first=step_interface(c,m,d,rs,hs,cb,force);if(!first)return nullptr;
 mj_step2(m,d);
 d->eq_active[weld]=0;mj_fwdPosition(m,d);mj_fwdVelocity(m,d);step_soft(m,d,q0,q1,v0,v1,p);
 auto last=step_interface(c,m,d,rs,hs,cb,force);if(!last){Py_DECREF(first);return nullptr;}
 mj_forward(m,d);auto out=PyTuple_Pack(2,first,last);Py_DECREF(first);Py_DECREF(last);return out;
}
struct OwnedRef{PyObject* p;explicit OwnedRef(PyObject* value):p(value){}~OwnedRef(){Py_XDECREF(p);}operator bool()const{return p!=nullptr;}};
// N10: retain all original sample/model/allocator/residual calls in order.
// Only the finite/max and Python loop dispatch are compiled.
static PyObject* mechanics_loop(PyObject*,PyObject* args){
 PyObject *model,*schedule,*times,*norm;if(!PyArg_ParseTuple(args,"OOOO",&model,&schedule,&times,&norm))return nullptr;
 OwnedRef grid((PyObject*)PyArray_FROM_OTF(times,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO));if(!grid)return nullptr;auto a=(PyArrayObject*)grid.p;auto t=(double*)PyArray_DATA(a);double peak_force=0.,peak_moment=0.,peak_residual=0.;bool finite=true;
 for(npy_intp i=0;i<PyArray_SIZE(a);i++){
  OwnedRef sample(PyObject_CallMethod(schedule,"sample","d",t[i]));if(!sample)return nullptr;
  OwnedRef q(PyObject_GetAttrString(sample.p,"q_rad")),v(PyObject_GetAttrString(sample.p,"dq_rad_s")),ddq(PyObject_GetAttrString(sample.p,"ddq_rad_s2"));if(!q||!v||!ddq)return nullptr;
  OwnedRef action(PyObject_CallMethod(model,"inverse_dynamics","OOO",q.p,v.p,ddq.p));if(!action)return nullptr;
  OwnedRef allocation(PyObject_CallMethod(model,"allocate_generalized_action","OO",action.p,q.p));if(!allocation)return nullptr;
  auto force_vector=PyDict_GetItemString(allocation.p,"force_world_n"),wrench=PyDict_GetItemString(allocation.p,"wrench_world");if(!force_vector||!wrench){PyErr_SetString(PyExc_KeyError,"mechanics allocation fields");return nullptr;}
  OwnedRef force_object(PyObject_CallOneArg(norm,force_vector));if(!force_object)return nullptr;double force=PyFloat_AsDouble(force_object.p);
  OwnedRef start(PyLong_FromLong(3)),slice(PySlice_New(start.p,Py_None,Py_None));if(!start||!slice)return nullptr;OwnedRef moment_vector(PyObject_GetItem(wrench,slice.p));if(!moment_vector)return nullptr;
  OwnedRef moment_object(PyObject_CallOneArg(norm,moment_vector.p));if(!moment_object)return nullptr;double moment=PyFloat_AsDouble(moment_object.p);
  double x[4],action_values[2],residual_values[2];if(!array_copy(q.p,x,2)||!array_copy(v.p,x+2,2)||!array_copy(action.p,action_values,2))return nullptr;
  OwnedRef state(array(x,4));if(!state)return nullptr;OwnedRef residual_object(PyObject_CallMethod(model,"state_residual_nm","O",state.p));if(!residual_object||!array_copy(residual_object.p,residual_values,2))return nullptr;
  double r0=std::abs(residual_values[0]),r1=std::abs(residual_values[1]);double residual=(std::isnan(r0)||std::isnan(r1))?NAN:((r0>r1)?r0:r1);
  finite=finite&&std::isfinite(action_values[0])&&std::isfinite(action_values[1])&&std::isfinite(force+moment);
  if(force>peak_force)peak_force=force;if(moment>peak_moment)peak_moment=moment;if(residual>peak_residual)peak_residual=residual;
  if(PyErr_Occurred())return nullptr;
 }
 return Py_BuildValue("(dddO)",peak_force,peak_moment,peak_residual,finite?Py_True:Py_False);
}
static PyMethodDef methods[]={{"plant_single_step",plant_single_step,METH_VARARGS,nullptr},{"create",create,METH_VARARGS,nullptr},{"mechanics_loop",mechanics_loop,METH_VARARGS,nullptr},{"quintic_sample",quintic_sample,METH_VARARGS,nullptr},{"raw_value_tree",raw_value_tree,METH_VARARGS,nullptr},{"observer_invert",observer_invert,METH_VARARGS,nullptr},{"planar_jacobian",planar_jacobian,METH_VARARGS,nullptr},{"regressor2",regressor2,METH_VARARGS,nullptr},{"table_margins",table_margins,METH_VARARGS,nullptr},{"state_features4",state_features4,METH_VARARGS,nullptr},{"validate_rigid",validate_rigid,METH_VARARGS,nullptr},{"soft_limit_arrays",soft_limit_arrays,METH_VARARGS,nullptr},{"apply_soft_limits",apply_soft_limits,METH_VARARGS,nullptr},{"cross3",cross_vector,METH_VARARGS,nullptr},{"rotvec_exact",rotation_vector,METH_VARARGS,nullptr},{"evaluate_arrays",evaluate_arrays,METH_VARARGS,nullptr},{"evaluate_data",evaluate_data,METH_VARARGS,nullptr},{"apply_wrenches",apply_wrenches,METH_VARARGS,nullptr},{nullptr,nullptr,0,nullptr}};
static PyModuleDef module={PyModuleDef_HEAD_INIT,"fast_native",nullptr,-1,methods};
PyMODINIT_FUNC PyInit_fast_native(){static_assert(sizeof(mjtNum)==sizeof(double),"MuJoCo dtype mismatch");import_array();auto np=PyImport_ImportModule("numpy");if(!np)return nullptr;matmul=PyObject_GetAttrString(np,"matmul");Py_DECREF(np);if(!matmul)return nullptr;auto enums=PyImport_ImportModule("enum");if(!enums)return nullptr;enum_class=PyObject_GetAttrString(enums,"Enum");Py_DECREF(enums);if(!enum_class)return nullptr;return PyModule_Create(&module);}
