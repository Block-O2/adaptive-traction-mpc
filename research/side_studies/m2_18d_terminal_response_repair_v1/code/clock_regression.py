from pathlib import Path
import sys,json,types
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc,causal_clock as c,numpy as np
class Clock:
 def __init__(self,t):self.t=t
 def __call__(self):return self.t
def main():
 from traction_mpc_stage5.full3d_adaptive_integration_v1.online_planning import PlanLifecycle
 c.install()
 rows=[]
 for offset,writecost,stepcost in [(0,0,10000),(1,20000,10000),(249999,1,10000),(250000,250001,10000),(4300123,4000,10000),(99975000,300000,10000)]:
  clock=Clock(10**9+offset);plant=types.SimpleNamespace(data=types.SimpleNamespace(ctrl=np.array([1.]),time=0.),last_joint_torque=np.array([1.]))
  self=types.SimpleNamespace(clock=clock,epoch_ns=10**9,steps=0,dt_ns=250000,dt=.00025,origin_physics_s=0.,plant=plant,runtime={'model_sequence':7},applied_commands=[],active_receipt_index=0,limit_violations=[])
  old_receipt=dict(receipt_index=0,applied=True,native_steps=0,apply_ns=None);self.applied_commands=[old_receipt]
  events=[]
  def step():
   events.append((self.steps,self.active_receipt_index,float(plant.data.ctrl[0])));self.steps+=1;plant.data.time=self.steps*self.dt;clock.t+=stepcost
  self._step=step;self.catch_up=lambda reason:None
  ready=clock();target=(ready-self.epoch_ns+self.dt_ns-1)//self.dt_ns
  receipt=dict(receipt_index=1,effective_activation_ns=self.epoch_ns+target*self.dt_ns,source_capture_ns=self.epoch_ns,native_steps=0,applied=False)
  self.applied_commands.append(receipt)
  life=PlanLifecycle(clock=clock,process_worker=False);life.capture(0.,self.epoch_ns);request=life.request('TASK',0.,asynchronous=False)
  self.runtime.update(plan_lifecycle=life,plan_to_activate=request)
  while self.steps<target:step()
  def write():plant.data.ctrl[0]=2.;plant.last_joint_torque[0]=2.;clock.t+=writecost
  error=None
  try:
   life.activate(request,lambda:c.apply(self,types.SimpleNamespace(),write,source_sample_time_s=0.,catchup=False,prepared=receipt),effective_activation_ns=receipt['effective_activation_ns'],applied_receipt=receipt);step()
  except RuntimeError as e:error=str(e)
  for index,owner,torque in events:
   if owner==1:
    assert self.epoch_ns+index*self.dt_ns>=receipt['apply_ns'];assert torque==2.
   else:assert torque==1.
  if receipt.get('applied'):assert 0<=receipt['quantization_delay_ns']<self.dt_ns
  else:assert all(owner==0 for _,owner,_ in events)
  native=life.records()[0]
  if receipt.get('applied'):assert native['effective_activation_ns']==receipt['effective_activation_ns'] and native['outcome']=='ACTIVATED'
  rows.append(dict(offset_ns=offset,write_cost_ns=writecost,steps=len(events),receipt=sc.clean(receipt),lifecycle=native,error=error))
 sc.save('CLOCK_C1b_LOCAL_REGRESSION.json',dict(status='PASS',no_physics=True,rows=rows,source_sha256=sc.sha(S/'code/causal_clock.py'),rule='ceil(actual command available /250000ns); all preceding intervals retain old command, write-once native lifecycle event, no integrated-state rollback',long_integer_grid_check=dict(steps=1600000,time_s=1600000*.00025,nanoseconds=1600000*250000)))
 print('CLOCK_C1_LOCAL_PASS',len(rows))
if __name__=='__main__':main()
