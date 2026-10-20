from pathlib import Path
import sys,time,pickle,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_early_return_motion_repair_v1');sys.path.insert(0,str(S/'code'))
import study_common as sc
def main():
 ident=sys.argv[1];p=S/'inputs'/(ident+'_controller_inputs.pkl');rows=pickle.loads(p.read_bytes());latency=[];errors=[]
 for _ in range(10):
  for context,actions,expected in rows:
   start=time.monotonic_ns();actual=context.preview_command_batch(actions);latency.append((time.monotonic_ns()-start)/1e6)
   errors.append(float(np.max(np.abs(actual.joint_torque_command_nm-expected.joint_torque_command_nm))))
 assert max(errors)==0.,max(errors)
 result=dict(status='PASS',input_sha256=sc.sha(p),no_physics=True,contexts=len(rows),calls=len(latency),ms=dict(zip(('p50','p95','p99','max'),np.percentile(latency,[50,95,99,100]).tolist())),max_torque_error=max(errors),scope='causal saved loaded command preview; attribution subset, not full feedback or plant qualification')
 sc.save(ident+'_CONTROLLER_REPLAY.json',result);print(result)
if __name__=='__main__':main()
