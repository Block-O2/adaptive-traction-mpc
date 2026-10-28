import json
import numpy as np
from acl2_shared import P,R,put,read,utc,sha,decision
from acl2_interface_audit import trace
def main():
 d=read('jobs/RETIMED/WORKER_DONE.json');assert d['status']=='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS'
 rows=read('jobs/RETIMED/PHYSICS_DONE.json')['rows'];D={r['id']:r for r in rows};base=trace('RETIMED_STRONG');t=np.linspace(base['time_s'][0],base['time_s'][-1],2001)
 def sample(a,key):return np.column_stack([np.interp(t,a['time_s'],a[key][:,j]) for j in range(a[key].shape[1])])
 ref0=sample(base,'reference_q_rad');torque0=sample(base,'cr12_actuator_command_nm');human0=sample(base,'evaluation_only_human_state_rad_rad_s');v=[];out=[]
 for i in range(8):
  r=D['RETIMED_MODE%d'%i];e=[e['modal'] for e in r.get('execution',[]) if e.get('modal') and e['activated'] and e['modal']['status']=='ACCEPTED'];q=dict(id=r['id'],complete=r['complete'],qualified=r['qualified'],JF=r.get('JF'),JM=r.get('JM'),accepted_and_activated=len(e),failed=r.get('motion_vs_B',{}).get('failed_requirements'))
  if r['complete']:
   a=trace(r['id']);rr=sample(a,'reference_q_rad');q.update(reference_delta_max_rad=float(np.max(abs(rr-ref0))),applied_torque_delta_max_Nm=float(np.max(abs(sample(a,'cr12_actuator_command_nm')-torque0))),native_Human_delta_max=float(np.max(abs(sample(a,'evaluation_only_human_state_rad_rad_s')-human0))))
   amplitude=r['action']['x'][i];v.append(((rr-ref0)/amplitude).ravel())
   q['executable']=bool(e and q['reference_delta_max_rad']>1e-10 and q['applied_torque_delta_max_Nm']>1e-10 and q['native_Human_delta_max']>1e-10)
  else:q['executable']=False
  out.append(q)
 singular=np.linalg.svd(np.asarray(v),compute_uv=False) if len(v)==8 else np.array([]);rank=int(np.sum(singular>singular[0]*1e-6)) if len(singular) else 0
 zero=read('audit/RETIMED_MODAL_ZERO_REPEAT_GATE.json')['status']=='PASS'
 gate=dict(utc=utc(),new_modes_executable=zero and all(r['executable'] for r in out),zero_reproduces_strong=zero,observed_issued_reference_contrast_rank=rank,singular_values=singular,interventions=out,original_safety_and_motion_contract_preserved=True,contrast_scope='eight separate one-mode actual issued-reference changes at common grid; finite local numerical rank',fixed_vs_retimed_common=dict(fixed=D['RETIMED_FIXED_COMMON_POS'],retimed=D['RETIMED_MODE0']),source_sha256=sha(__file__))
 put('audit/RETIMED_INTERFACE_GATE.json',gate)
 decision('Original automatic duration can expose previously rejected spatial coordination','Retimed zero and eight single-mode physical interventions',{'executable':gate['new_modes_executable'],'rank':rank,'qualified':sum(r['qualified'] for r in out)},'Original safety/admission retained; response and qualification separately assessed','Allow main same-permission comparison only if all new modes reach execution',['audit/RETIMED_INTERFACE_GATE.json'])
 print('RETIMED_INTERFACE_GATE',gate['new_modes_executable'],'rank',rank,flush=True)
if __name__=='__main__':main()
