from task_bootstrap import *
def chain(f):
 out=[]
 while f is not None:
  out.append(dict(name=f.__name__,module=f.__module__,file=f.__code__.co_filename));f=getattr(f,'__wrapped__',None)
 return out
def main():
 import study_common as sc
 case,options=sc.load_case_options()
 print(json.dumps(dict(options=options)))
 import profiling_instrumentation as profile
 profile.install()
 from optimized_e3 import E3Interface
 x=E3Interface(dict(timing_version='E3',method='M2',weights=str(STUDY/'weights/frozen_Q_v1')))
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 import q_first_method,certified_snapshot
 print(json.dumps(dict(submit=chain(op.PlanLifecycle.submit),compute=chain(op.PlanLifecycle.compute),execute=chain(op.execute_task_snapshot),native_local=chain(q_first_method.native_local),INSTALLED=certified_snapshot.INSTALLED)))
 # The threaded executor must dispatch the patched exact-byte function.
 lifecycle=op.PlanLifecycle();lifecycle.capture(0,time.monotonic_ns());req=lifecycle.request('TASK',0,asynchronous=True)
 try:lifecycle.submit(req,b'not-a-valid-pickle').result()
 except Exception as e:print(json.dumps(dict(expected_error=str(e),events=certified_snapshot.EVENTS)))
 lifecycle.close()
if __name__=='__main__':main()
