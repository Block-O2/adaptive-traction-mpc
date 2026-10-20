"""Finite process worker. Inputs contain no plant, runtime or truth state."""
import pickle,time,os
def warm():
 import study_common as sc
 def forbidden(*a,**kw):raise AssertionError('SLOW_OWNER_MAY_NOT_CREATE_PLANT')
 sc.SACExpertEnv.__init__=forbidden
 sc.rt._initialize_loaded_runtime=forbidden
 return dict(pid=os.getpid(),ready_ns=time.monotonic_ns(),plant_owner=False)
def execute(kind,payload):
 import study_common as sc
 start=time.monotonic_ns();args,kwargs=pickle.loads(payload)
 fn={'commissioning_target':sc.rt.choose_feedback_commissioning_target,'commissioning_fit':sc.rt._fit_and_replay_commissioning}[kind]
 value=fn(*args,**kwargs)
 return dict(worker_start_ns=start,proposal_ready_ns=time.monotonic_ns(),pid=os.getpid(),kind=kind,payload=pickle.dumps((value,args,kwargs),protocol=5))

def task_with_certificates(payload):
 warm()
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 import admission_certificates
 result=op._process_task_snapshot(payload)
 if 'value' in result:
  result['multirate_mechanics_certificates']=admission_certificates.prepare(payload,result['value'])
 result['proposal_ready_ns']=time.monotonic_ns()
 return result
