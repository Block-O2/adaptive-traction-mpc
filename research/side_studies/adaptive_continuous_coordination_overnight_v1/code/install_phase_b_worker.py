from task_bootstrap import *
import ast
def main():
 p=STUDY/'code/worker.py';text=p.read_text()
 old="   if request.get('timing_version','T0')!='T0' and request.get('method')!='M0':"
 new="   if request.get('timing_version','T0').startswith('E3') and request.get('method')!='M0':\n    from optimized_e3 import E3Interface\n    interface=E3Interface(request)\n   elif request.get('timing_version','T0')!='T0' and request.get('method')!='M0':"
 assert old in text;text=text.replace(old,new)
 text=text.replace('   import numpy as np','   import numpy as np')
 old='  import numpy as np';assert old in text
 text=text.replace(old,'  import public_worker,batched_mechanics\n  public_worker.install(request);batched_mechanics.install(request)\n'+old,1)
 old=" if 'profile' in locals():save(request['id']+'_TIMING_PROFILE.json',profile.evidence())";assert old in text
 text=text.replace(old," if 'batched_mechanics' in locals() and batched_mechanics.EVENTS:save(request['id']+'_BATCHED_MECHANICS.json',dict(rows=batched_mechanics.EVENTS,batch_calls=len(batched_mechanics.EVENTS),component_evaluations=sum(e['sample_count'] for e in batched_mechanics.EVENTS),no_control_law_changes=True))\n"+old)
 ast.parse(text);p.write_text(text);print('PHASE_B_ROUTE_AND_TWO_PUBLIC_VERSIONS_INSTALLED')
if __name__=='__main__':main()
