from pathlib import Path
import sys,json,types,time
S=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2/runtime');sys.path.insert(0,str(S/'code'))
def main():
 import study_common as sc
 from service_clock import next_control_tick
 rows=[]
 for last_poll in (0,1,2000000):
  target=(last_poll+1)*5000000
  for offset in (-2000000,0,250000,1000000,20000000):
   now=target+offset;sleeps=[];caught=[]
   fake=types.SimpleNamespace(epoch_ns=0,_last_poll_grid=last_poll,sensor_steps=20,dt_ns=250000,steps=(now//250000),clock=lambda:now,sleeper=sleeps.append,catch_up=caught.append)
   next_control_tick(fake)
   assert sleeps==([max(0,-offset)/1e9] if offset<0 else [])
   assert len(caught)==1 and fake.steps==now//250000
   rows.append(dict(last_poll_grid=last_poll,actual_now_ns=now,next_service_deadline_ns=target,sleep_s=sleeps,one_actual_catchup=True,no_backfilled_calls=True))
 # Scientific scheduling keeps its own original next_control_tick method.
 from traction_mpc_stage5.full3d_adaptive_integration_v1.scientific_scheduler import ScientificPhysicsSession
 assert 'next_control_tick' in ScientificPhysicsSession.__dict__
 out=dict(status='PASS',clock_version='C2_POLL_DEADLINE_ACTUAL_SERVICE',registered_unix=time.time(),cases=rows,scientific_override_retained=True,source_sha256=sc.sha(S/'code/service_clock.py'),policy='Preserve 5ms absolute service grid. If the next deadline elapsed during work, service once now using current sensor data. Old controls remain during unsimulated past; C1b ceil actual write ownership unchanged. No artificial callback timestamps or changed controller/planner/physical requirements.')
 sc.save('CLOCK_C2_SERVICE_LOCAL_REGRESSION.json',out);print(json.dumps(out))
if __name__=='__main__':main()
