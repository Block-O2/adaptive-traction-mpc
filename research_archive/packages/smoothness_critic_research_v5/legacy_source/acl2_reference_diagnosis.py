"""Post-execution reference-load reconstruction; never a proposal input."""
from pathlib import Path
import os,sys,json,time
import numpy as np
from acl2_shared import P,R,put,read,sha,utc
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage4.cuff_allocator import CuffAwareSagittalAllocator
from traction_mpc_stage5.high_rom_v1 import deployable_prior

def main():
 start=time.time();belief=read('history/CAUSAL_COMMISSIONED_BELIEF.json');geometry=PlanarCuffGeometry(**{k:np.asarray(v) if isinstance(v,list) else v for k,v in belief['geometry'].items()});model=sc.rt.StateResidualHumanModel(geometry,np.asarray(belief['beta']),deployable_prior(),residual_weights_nm=np.asarray(belief['residual_weights_nm']));alloc=CuffAwareSagittalAllocator();table=read('models/MODAL_NOMINAL_TABLE.json')
 def arithmetic(ident,stride):
  path=R/'source/results'/ident/'trace.npz';su=read('runtime/source/results/'+ident+'/summary.json')
  with np.load(path) as z:
   task=np.flatnonzero(z['stage']=='TASK');ix=task[np.unique(np.r_[np.arange(0,len(task),stride),len(task)-1])];t=z['time_s'][ix];q=z['reference_q_rad'][ix];v=z['reference_dq_rad_s'][ix];a=z['reference_ddq_rad_s2'][ix]
  w=[]
  for qq,vv,aa in zip(q,v,a):w.append(alloc._prepare_factors(qq,model).action_to_wrench_world@model.inverse_dynamics(qq,vv,aa))
  w=np.asarray(w);dt=np.diff(t);force=np.linalg.norm(w[:,:3],axis=1);moment=np.linalg.norm(w[:,3:],axis=1);phase=np.full(len(t),'OUTBOUND',dtype='<U10')
  for tr in su['task']['phase_transitions']:
   if tr['to'] in ['OUTBOUND','HOLD','RETURN']:phase[t>=tr['time_s']-1e-9]=tr['to']
  return dict(issued_reference_nominal_JF=float(force[:-1]@dt),issued_reference_nominal_JM=float(moment[:-1]@dt),phase_JF={ph:float(force[:-1][phase[:-1]==ph]@dt[phase[:-1]==ph]) for ph in ['OUTBOUND','HOLD','RETURN']},reference_samples=len(t),source_trace_sha256=sha(path),post_execution_inputs=True)
 base=read('attempts/RETIMED_STRONG_RESULT.json');base_nom=arithmetic(base['id'],1);rows=[]
 for k in range(8):
  ident='RETIMED_MODE%d'%k;r=read('attempts/'+ident+'_RESULT.json')
  if not r['complete']:continue
  actualnom=arithmetic(ident,1);x=np.asarray(r['action']['x']);before=np.asarray(table['center'])+x@np.asarray(table['linear']).T+(x*x)@np.asarray(table['quadratic']).T;d_before=before[0]-table['center'][0];d_issued=actualnom['issued_reference_nominal_JF']-base_nom['issued_reference_nominal_JF'];d_actual=r['JF']-base['JF']
  rows.append(dict(id=ident,x=x,qualified=r['qualified'],actual_JF=r['JF'],actual_JM=r['JM'],delta_JF_actual=d_actual,delta_JF_pre_execution_approximation=float(d_before),delta_JF_posthoc_actual_issued_reference=float(d_issued),reference_approximation_gap=float(d_issued-d_before),remaining_closed_loop_and_model_gap=float(d_actual-d_issued),posthoc_issued_reference_nominal=actualnom,sign_before_correct=bool(np.sign(d_before)==np.sign(d_actual)),sign_after_correct=bool(np.sign(d_issued)==np.sign(d_actual))))
 before_err=np.asarray([r['delta_JF_pre_execution_approximation']-r['delta_JF_actual'] for r in rows]);after_err=np.asarray([r['delta_JF_posthoc_actual_issued_reference']-r['delta_JF_actual'] for r in rows]);out=dict(utc=utc(),kind='POSTHOC_EXECUTED_REFERENCE_LOAD_RECONSTRUCTION_NOT_FORWARD_PREDICTION',scope='eight development interventions at fixed nominal Human/prefix; no new native computation; no optimizer/model feedback',base_actual=base,base_issued_reference_nominal=base_nom,rows=rows,diagnostic_RMSE_deltaJF_before=float(np.sqrt(np.mean(before_err**2))),diagnostic_RMSE_deltaJF_after=float(np.sqrt(np.mean(after_err**2))),correct_sign_before=sum(r['sign_before_correct'] for r in rows),correct_sign_after=sum(r['sign_after_correct'] for r in rows),n=len(rows),wall_s=time.time()-start,new_native_steps=0,limitation='Uses each candidate already issued reference q/dq/ddq after execution, therefore cannot be used as a pre-execution performance claim or causal mediation fraction. Remaining gap mixes model error, tracking, feedback, allocation and contact.',source_sha256=sha(__file__))
 put('audit/REFERENCE_RESPONSE_MECHANISM.json',out);print('REFERENCE_DIAGNOSIS',out['diagnostic_RMSE_deltaJF_before'],out['diagnostic_RMSE_deltaJF_after'],'signs',out['correct_sign_before'],out['correct_sign_after'],flush=True)
if __name__=='__main__':main()
