from task_bootstrap import *
import ast
def main():
 p=STUDY/'code/optimized_e3.py';text=p.read_text();old='   with shared_nominal.boundary(b):return super(OptimizedNativeInterface,self).decision_boundary(b)'
 new="   with shared_nominal.boundary(b):\n    result=super(OptimizedNativeInterface,self).decision_boundary(b)\n    if self.request.get('certify_final_payload'):\n     import certified_apply\n     certified_apply.ensure(self.certificate_module,b)\n    return result"
 assert old in text;text=text.replace(old,new).replace("  capture_states.finish(metric['name'])","  capture_states.finish(metric['name'])\n  if self.request.get('certify_final_payload'):\n   import certified_apply\n   from study_common import save\n   save(metric['name']+'_FINAL_PAYLOAD_CERTIFICATION.json',dict(rows=certified_apply.EVENTS))");ast.parse(text);p.write_text(text);shutil.copy2(p,Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/optimized_e3.py'));print('ACTUAL_SUBMITTED_PAYLOAD_CERTIFICATE_READY')
if __name__=='__main__':main()
