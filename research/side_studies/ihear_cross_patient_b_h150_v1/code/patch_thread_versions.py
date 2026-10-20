from task_bootstrap import *
import ast
def main():
 p=STUDY/'code/public_worker.py';text=p.read_text().replace("if request.get('public_version')!='C1':return","if request.get('public_version') not in ('C1','C1_THREAD','C2_THREAD'):return").replace("options['planner_process_worker']=True","options['planner_process_worker']=request.get('public_version')=='C1'");ast.parse(text);p.write_text(text)
 # Keep the authoring copy aligned; sync must never revert a version silently.
 shutil.copy2(p,Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/public_worker.py'))
 p=STUDY/'code/batched_mechanics.py';text=p.read_text().replace("request.get('public_version')!='C2'","request.get('public_version') not in ('C2','C2_THREAD')");ast.parse(text);p.write_text(text);shutil.copy2(p,Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/batched_mechanics.py'))
 p=STUDY/'code/optimized_e3.py';text=p.read_text().replace('  from q_first_method import QFirstInterface','  import capture_states\n  capture_states.capture(self,b,c)\n  from q_first_method import QFirstInterface').replace('  super().finish(env,metric)','  super().finish(env,metric)\n  import capture_states\n  capture_states.finish(metric[\'name\'])')
 text=text.replace('super().__init__(request);certified_snapshot.install()',"super().__init__(request)\n  if request.get('certificate_version')=='v2':\n   import certified_snapshot_v2\n   self.certificate_module=certified_snapshot_v2\n  else:self.certificate_module=certified_snapshot\n  self.certificate_module.install()")
 text=text.replace('with certified_snapshot.boundary(b):','with self.certificate_module.boundary(b):').replace('rows=certified_snapshot.EVENTS','rows=self.certificate_module.EVENTS');ast.parse(text);p.write_text(text);shutil.copy2(p,Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/optimized_e3.py'))
 print('THREAD_LIFECYCLE_AND_SCI_ONLY_CAUSAL_STATE_CAPTURE_READY')
if __name__=='__main__':main()
