"""Audit executed authority, not symbolic parameter count."""
from pathlib import Path
import json,collections
import numpy as np
from acl2_shared import P,R,read,put,utc,sha,decision
def trace(ident):
 with np.load(R/'source/results'/ident/'trace.npz') as z:
  task=z['stage']=='TASK';return {k:z[k][task].copy() for k in ['time_s','reference_q_rad','reference_dq_rad_s','cr12_actuator_command_nm','evaluation_only_human_state_rad_rad_s']}
def main():
 done=read('jobs/INTERFACE/WORKER_DONE.json');assert done['status']=='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS','INTERFACE_WORKER_NOT_COMPLETE'
 rows=read('jobs/INTERFACE/PHYSICS_DONE.json')['rows'];byid={r['id']:r for r in rows};base=trace('INTERFACE_H150');t=np.linspace(base['time_s'][0],base['time_s'][-1],2001)
 def sampled(a,key):return np.column_stack([np.interp(t,a['time_s'],a[key][:,j]) for j in range(a[key].shape[1])])
 ref0=sampled(base,'reference_q_rad');torque0=sampled(base,'cr12_actuator_command_nm');human0=sampled(base,'evaluation_only_human_state_rad_rad_s');results=[];vectors=[]
 for i in range(8):
  pair=[]
  for sign in ['POS','NEG']:
   ident='INTERFACE_MODE%d_%s'%(i,sign);row=byid[ident];r=dict(id=ident,complete=row['complete'],qualified=row['qualified'],JF=row.get('JF'),JM=row.get('JM'),failed_requirements=row.get('motion_vs_B',{}).get('failed_requirements'))
   if row['complete']:
    a=trace(ident);ref=sampled(a,'reference_q_rad');torque=sampled(a,'cr12_actuator_command_nm');human=sampled(a,'evaluation_only_human_state_rad_rad_s')
    executed=[e for e in row['execution'] if e.get('modal') and e['modal']['status']=='ACCEPTED' and e['activated']]
    r.update(proposed=len([e for e in row['execution'] if e.get('modal')]),accepted=sum(e['modal']['status']=='ACCEPTED' for e in row['execution'] if e.get('modal')),activated=len(executed),rejected=sum(e['modal']['status']=='REJECTED' for e in row['execution'] if e.get('modal')),actual_issued_reference_max_delta_rad=float(np.max(abs(ref-ref0))),actual_applied_torque_max_delta_Nm=float(np.max(abs(torque-torque0))),actual_Human_motion_max_delta=float(np.max(abs(human-human0))))
    r['executable']=bool(executed and r['actual_issued_reference_max_delta_rad']>1e-10 and r['actual_applied_torque_max_delta_Nm']>1e-10 and r['actual_Human_motion_max_delta']>1e-10);pair.append(ref)
   else:r['executable']=False
   results.append(r)
  if len(pair)==2:vectors.append(((pair[0]-pair[1])/.7).ravel())
 singular=np.linalg.svd(np.asarray(vectors),compute_uv=False) if len(vectors)==8 else np.array([])
 rank=int(np.sum(singular>singular[0]*1e-6)) if len(singular) else 0
 zero=read('audit/INTERFACE_MODAL_ZERO_REPEAT_GATE.json');coord=read('audit/INTERFACE_A1_ROTATED_REPEAT_GATE.json')
 gate=dict(utc=utc(),zero_reproduces_H150=zero['status']=='PASS',same_family_coordinate_identity=coord['status']=='PASS',new_modes_executable=all(any(r['executable'] for r in results if r['id'].startswith('INTERFACE_MODE%d_'%i)) for i in range(8)),observed_issued_reference_contrast_rank=rank,rank_scope='numerical rank of fixed-grid plus/minus actual issued-reference contrasts, not a proof of globally independent nonlinear degrees of freedom',singular_values=singular,mode_interventions=results,full_physics_interface_only=True,mode_names=['O_common_path','O_relative_path','R_common_path','R_relative_path','O_local_time','R_local_time','O_pass_speed','R_pass_speed'],safety_scorer_and_plant_changed=False,source_sha256=sha(__file__))
 assert gate['zero_reproduces_H150'] and gate['same_family_coordinate_identity'],'ZERO_OR_COORDINATE_IDENTITY_FAILED'
 put('audit/INTERFACE_GATE.json',gate)
 decision('Eight new phase path/time/pass-speed modes must reach real execution','Zero/same-family identity and +/- eight native interventions',{'new_modes_executable':gate['new_modes_executable'],'contrast_rank':rank,'qualified_interventions':sum(r['qualified'] for r in results)},'Accepted/activated plans, issued reference, applied torque and actual Human changes are checked separately','Build bounded offline nominal proxy and allocate comparison only if all modes execute',['audit/INTERFACE_GATE.json'])
 print('INTERFACE_GATE',gate['new_modes_executable'],'contrast_rank',rank,flush=True)
if __name__=='__main__':main()
