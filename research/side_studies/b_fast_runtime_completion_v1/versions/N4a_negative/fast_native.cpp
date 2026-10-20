#define PY_SSIZE_T_CLEAN
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
#include <mujoco/mujoco.h>
#include <cstring>
#include <cmath>
static PyObject* matmul=nullptr;
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
  if(q[i]<lower){double z=(lower-q[i])/p[4];torque[i]=p[6]*std::pow(z,3.);torque[i]+=(p[7]*std::pow(z,2.))*((-dq[i]>0.)?-dq[i]:0.);}
  else if(q[i]>upper){double z=(q[i]-upper)/p[4];torque[i]=(-p[6])*std::pow(z,3.);torque[i]-=(p[7]*std::pow(z,2.))*((dq[i]>0.)?dq[i]:0.);}
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
 for(int i=0;i<m->nv;i++)d->qfrc_applied[i]=0.;d->qfrc_applied[v0]=out[0];d->qfrc_applied[v1]=out[1];Py_RETURN_NONE;
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
static PyMethodDef methods[]={{"create",create,METH_VARARGS,nullptr},{"soft_limit_arrays",soft_limit_arrays,METH_VARARGS,nullptr},{"apply_soft_limits",apply_soft_limits,METH_VARARGS,nullptr},{"cross3",cross_vector,METH_VARARGS,nullptr},{"rotvec_exact",rotation_vector,METH_VARARGS,nullptr},{"evaluate_arrays",evaluate_arrays,METH_VARARGS,nullptr},{"evaluate_data",evaluate_data,METH_VARARGS,nullptr},{"apply_wrenches",apply_wrenches,METH_VARARGS,nullptr},{nullptr,nullptr,0,nullptr}};
static PyModuleDef module={PyModuleDef_HEAD_INIT,"fast_native",nullptr,-1,methods};
PyMODINIT_FUNC PyInit_fast_native(){static_assert(sizeof(mjtNum)==sizeof(double),"MuJoCo dtype mismatch");import_array();auto np=PyImport_ImportModule("numpy");if(!np)return nullptr;matmul=PyObject_GetAttrString(np,"matmul");Py_DECREF(np);if(!matmul)return nullptr;return PyModule_Create(&module);}
