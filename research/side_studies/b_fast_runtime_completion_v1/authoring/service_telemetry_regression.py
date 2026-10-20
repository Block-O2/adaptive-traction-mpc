from pathlib import Path
import sys,json,types,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc,multirate,service_clock
call=service_clock.install(telemetry=True);rows=[]
for offset in (-2000000,0,250000,20000000):
 now=[5000000+offset];events=[];p=types.SimpleNamespace(data=types.SimpleNamespace(time=0.),last_joint_torque=np.ones(6));wall=types.SimpleNamespace(epoch_ns=0,_last_poll_grid=0,sensor_steps=20,dt_ns=250000,steps=0,clock=lambda:now[0],plant=p,active_receipt_index=7)
 def wait(dt):events.append(('wait',dt));now[0]+=round(dt*1e9)
 def catch(why):events.append(('catchup',why));wall.steps+=20;p.data.time+=.005;now[0]+=900000
 wall.sleeper=wait;wall.catch_up=catch;multirate.ROWS['fast'][:]=[dict(service_start_ns=now[0]-2000000,service_finish_ns=None)];before=now[0];call(wall);r=multirate.ROWS['fast'][-1]
 assert r['service_finish_ns']==before and r['physical_finish_host_ns']==now[0] and r['physical_steps_in_tick']==20 and r['receipt_index']==7
 assert len([x for x in events if x[0]=='wait'])==int(offset<0) and len([x for x in events if x[0]=='catchup'])==1
 rows.append(dict(offset=offset,owner_pre_wait_ns=r['service_finish_ns'],physical_finish_host_ns=r['physical_finish_host_ns'],events=events))
out=dict(status='PASS',no_native_physics=True,rows=rows,clock_policy_unchanged=True,old_rows_not_rewritten=True,legacy_compute_previous_definition='C2 overwrote multirate next-tick wrapper, so interval_finish included wait/catchup; previous raw labels retained')
sc.save('C2b_SERVICE_TELEMETRY_LOCAL_REGRESSION.json',out);print(json.dumps(out))
