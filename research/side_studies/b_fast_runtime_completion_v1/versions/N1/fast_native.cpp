#define PY_SSIZE_T_CLEAN
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
#include <mujoco/mujoco.h>
#include <cstring>
#include <cmath>
struct Context { double k[3],d[3],rest[3],R0[9],kr,dr,last[36]; bool valid=false; PyObject* value=nullptr; };
static void destroy(PyObject* cap){auto c=(Context*)PyCapsule_GetPointer(cap,"fast.interface.v1");if(c){Py_XDECREF(c->value);delete c;}}
static bool array_copy(PyObject* o,double* out,int n){auto a=(PyArrayObject*)PyArray_FROM_OTF(o,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO);if(!a)return false;if(PyArray_SIZE(a)!=n){Py_DECREF(a);PyErr_SetString(PyExc_ValueError,"fixed shape mismatch");return false;}std::memcpy(out,PyArray_DATA(a),n*sizeof(double));Py_DECREF(a);return true;}
static PyObject* array(const double* x,int n){npy_intp dims[]={n};auto a=PyArray_SimpleNew(1,dims,NPY_DOUBLE);if(a)std::memcpy(PyArray_DATA((PyArrayObject*)a),x,n*sizeof(double));return a;}
static double dot(const double* a,const double* b,int n){double r=0.;for(int i=0;i<n;i++)r+=a[i]*b[i];return r;}
static void cross(const double* a,const double* b,double* o){o[0]=a[1]*b[2]-a[2]*b[1];o[1]=a[2]*b[0]-a[0]*b[2];o[2]=a[0]*b[1]-a[1]*b[0];}
static void mv(const double* m,const double* x,double* o,bool transpose=false){for(int i=0;i<3;i++){o[i]=0.;for(int j=0;j<3;j++)o[i]+=m[transpose?j*3+i:i*3+j]*x[j];}}
static PyObject* create(PyObject*,PyObject* args){PyObject *k,*d,*r,*R;double kr,dr;if(!PyArg_ParseTuple(args,"OOOOdd",&k,&d,&r,&R,&kr,&dr))return nullptr;auto c=new Context;if(!array_copy(k,c->k,3)||!array_copy(d,c->d,3)||!array_copy(r,c->rest,3)||!array_copy(R,c->R0,9)){delete c;return nullptr;}c->kr=kr;c->dr=dr;return PyCapsule_New(c,"fast.interface.v1",destroy);}
// State order per site: position[3], rotation[9], world angular[3], world linear[3].
static PyObject* evaluate(Context* c,const double* state,PyObject* rotvec){
 if(c->valid&&std::memcmp(c->last,state,36*sizeof(double))==0){Py_INCREF(c->value);return c->value;}
 auto rp=state;auto rr=state+3;auto rw=state+12;auto rv=state+15;auto hp=state+18;auto rh=state+21;auto hw=state+30;auto hv=state+33;
 double r[3],x[3],u[3],omega[3],temp[3],wxr[3],A[9],B[9];for(int i=0;i<3;i++)r[i]=rp[i]-hp[i];mv(rh,r,x,true);for(int i=0;i<3;i++)x[i]-=c->rest[i];cross(hw,r,wxr);for(int i=0;i<3;i++)temp[i]=(rv[i]-hv[i])-wxr[i];mv(rh,temp,u,true);for(int i=0;i<3;i++)temp[i]=rw[i]-hw[i];mv(rh,temp,omega,true);
 for(int i=0;i<3;i++)for(int j=0;j<3;j++){A[i*3+j]=0.;for(int n=0;n<3;n++)A[i*3+j]+=rh[n*3+i]*rr[n*3+j];}
 for(int i=0;i<3;i++)for(int j=0;j<3;j++){B[i*3+j]=0.;for(int n=0;n<3;n++)B[i*3+j]+=A[i*3+n]*c->R0[j*3+n];}
 npy_intp dims[]={3,3};auto matrix=PyArray_SimpleNew(2,dims,NPY_DOUBLE);if(!matrix)return nullptr;std::memcpy(PyArray_DATA((PyArrayObject*)matrix),B,sizeof(B));auto theta_object=PyObject_CallOneArg(rotvec,matrix);Py_DECREF(matrix);if(!theta_object)return nullptr;double theta[3];if(!array_copy(theta_object,theta,3)){Py_DECREF(theta_object);return nullptr;}Py_DECREF(theta_object);
 double force[3],couple[3],transport[3],human[6],robot[6],hvel[6],rvel[6],kx[3],du[3],ku[3];
 for(int i=0;i<3;i++){temp[i]=c->k[i]*x[i]+c->d[i]*u[i];kx[i]=c->k[i]*x[i];du[i]=c->d[i]*u[i];ku[i]=c->k[i]*u[i];}mv(rh,temp,force);
 for(int i=0;i<3;i++)temp[i]=c->kr*theta[i]+c->dr*omega[i];mv(rh,temp,couple);cross(r,force,transport);
 for(int i=0;i<3;i++){human[i]=force[i];human[i+3]=couple[i]+transport[i];robot[i]=-force[i];robot[i+3]=-couple[i];hvel[i]=hv[i];hvel[i+3]=hw[i];rvel[i]=rv[i];rvel[i+3]=rw[i];}
 auto result=PyTuple_New(10);if(!result)return nullptr;double* vectors[]={x,u,theta,omega,human,robot};int sizes[]={3,3,3,3,6,6};for(int i=0;i<6;i++){auto a=array(vectors[i],sizes[i]);if(!a){Py_DECREF(result);return nullptr;}PyTuple_SET_ITEM(result,i,a);}
 double scalars[]={.5*(dot(x,kx,3)+c->kr*dot(theta,theta,3)),dot(u,du,3)+c->dr*dot(omega,omega,3),dot(human,hvel,6)+dot(robot,rvel,6),dot(x,ku,3)+c->kr*dot(theta,omega,3)};
 for(int i=0;i<4;i++)PyTuple_SET_ITEM(result,i+6,PyFloat_FromDouble(scalars[i]));Py_XDECREF(c->value);c->value=result;Py_INCREF(result);std::memcpy(c->last,state,36*sizeof(double));c->valid=true;return result;
}
static PyObject* evaluate_arrays(PyObject*,PyObject* args){PyObject *cap,*a,*rotvec;if(!PyArg_ParseTuple(args,"OOO",&cap,&a,&rotvec))return nullptr;auto c=(Context*)PyCapsule_GetPointer(cap,"fast.interface.v1");if(!c)return nullptr;double state[36];if(!array_copy(a,state,36))return nullptr;return evaluate(c,state,rotvec);}
static PyObject* evaluate_data(PyObject*,PyObject* args){PyObject *cap,*rotvec;unsigned long long ma,da;int rs,hs;if(!PyArg_ParseTuple(args,"OKKiiO",&cap,&ma,&da,&rs,&hs,&rotvec))return nullptr;auto c=(Context*)PyCapsule_GetPointer(cap,"fast.interface.v1");if(!c)return nullptr;auto m=(mjModel*)(uintptr_t)ma;auto d=(mjData*)(uintptr_t)da;if(!m||!d||rs<0||hs<0||rs>=m->nsite||hs>=m->nsite){PyErr_SetString(PyExc_ValueError,"invalid owned MuJoCo state");return nullptr;}double state[36];int sites[]={rs,hs};for(int i=0;i<2;i++){double* o=state+i*18;std::memcpy(o,d->site_xpos+sites[i]*3,3*sizeof(double));std::memcpy(o+3,d->site_xmat+sites[i]*9,9*sizeof(double));mj_objectVelocity(m,d,mjOBJ_SITE,sites[i],o+12,0);}return evaluate(c,state,rotvec);}
static PyObject* apply_wrenches(PyObject*,PyObject* args){unsigned long long ma,da;int rs,hs;PyObject *human,*robot,*force;if(!PyArg_ParseTuple(args,"KKiiOOO",&ma,&da,&rs,&hs,&human,&robot,&force))return nullptr;auto m=(mjModel*)(uintptr_t)ma;auto d=(mjData*)(uintptr_t)da;auto h=(PyArrayObject*)PyArray_FROM_OTF(human,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO);auto r=(PyArrayObject*)PyArray_FROM_OTF(robot,NPY_DOUBLE,NPY_ARRAY_CARRAY_RO);auto f=(PyArrayObject*)PyArray_FROM_OTF(force,NPY_DOUBLE,NPY_ARRAY_CARRAY);if(!h||!r||!f){Py_XDECREF(h);Py_XDECREF(r);Py_XDECREF(f);return nullptr;}if(PyArray_SIZE(h)!=6||PyArray_SIZE(r)!=6||PyArray_SIZE(f)!=m->nv||rs<0||hs<0||rs>=m->nsite||hs>=m->nsite){Py_DECREF(h);Py_DECREF(r);Py_DECREF(f);PyErr_SetString(PyExc_ValueError,"invalid wrench shape/site");return nullptr;}auto hp=(double*)PyArray_DATA(h);auto rp=(double*)PyArray_DATA(r);auto fp=(double*)PyArray_DATA(f);for(int i=0;i<m->nv;i++)fp[i]=0.;mj_applyFT(m,d,hp,hp+3,d->site_xpos+hs*3,m->site_bodyid[hs],fp);mj_applyFT(m,d,rp,rp+3,d->site_xpos+rs*3,m->site_bodyid[rs],fp);for(int i=0;i<m->nv;i++)d->qfrc_applied[i]+=fp[i];Py_DECREF(h);Py_DECREF(r);Py_DECREF(f);Py_RETURN_NONE;}
static PyMethodDef methods[]={{"create",create,METH_VARARGS,nullptr},{"evaluate_arrays",evaluate_arrays,METH_VARARGS,nullptr},{"evaluate_data",evaluate_data,METH_VARARGS,nullptr},{"apply_wrenches",apply_wrenches,METH_VARARGS,nullptr},{nullptr,nullptr,0,nullptr}};
static PyModuleDef module={PyModuleDef_HEAD_INIT,"fast_native",nullptr,-1,methods};
PyMODINIT_FUNC PyInit_fast_native(){static_assert(sizeof(mjtNum)==sizeof(double),"MuJoCo dtype mismatch");import_array();return PyModule_Create(&module);}
