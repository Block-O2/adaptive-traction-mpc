"""Layered actual-reference and physical comparison, no trajectory matching claims from JF alone."""
import os,sys,json,gzip,hashlib
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path(__file__).resolve().parents[1];R=P/'runtime'
def load(ident):
 path=R/'source/results'/ident;m=json.loads((R/'reports'/(ident+'_MEASURED.json')).read_text());su=json.loads((path/'summary.json').read_text())
 with np.load(path/'trace.npz') as z:
  use=z['stage']=='TASK';tr={k:z[k][use] for k in ['time_s','reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2','evaluation_only_human_state_rad_rad_s']}
 with gzip.open(path/'runtime_artifacts.json.gz','rt') as f:raw=json.load(f)
 n=raw['wall_physics']['native_states_evaluation_only'];task=[x for x in n if tr['time_s'][0]-1e-9<=x['time_s']<=tr['time_s'][-1]+1e-9];native={'t':np.array([x['time_s'] for x in task]),'q':np.array([x['qpos_evaluation_only'] for x in task])[:,m['quality']['qpos_indices']],'v':np.array([x['qvel_evaluation_only'] for x in task])[:,m['quality']['qvel_indices']],'tau':np.array([x['command_torque_nm'] for x in task])};return m,su,tr,native,raw

def interp(t0,t,x):return np.column_stack([np.interp(t0,t,x[:,j]) for j in range(x.shape[1])])

def main():
 base=load('P1_BEST');rows=[]
 for f in sorted((P/'attempts').glob('*_RESULT.json')):
  r=json.loads(f.read_text());ident=r['id']
  if not ident.startswith(('P1_','MATCH_')) or not r['complete']:continue
  m,su,tr,native,raw=load(ident);b,sb,tb,nb,rb=base;delta={}
  for k,unit in [('reference_q_rad','deg'),('reference_dq_rad_s','deg/s'),('reference_ddq_rad_s2','deg/s2'),('evaluation_only_human_state_rad_rad_s','mixed_deg_deg/s')]:delta[k+'_max_abs_by_joint']=np.degrees(np.max(abs(tr[k]-interp(tr['time_s'],tb['time_s'],tb[k])),axis=0)).tolist()
  for k in ['q','v','tau']:
   diff=native[k]-interp(native['t'],nb['t'],nb[k]);delta['native_'+k+'_max_abs_by_joint']=((np.degrees(np.max(abs(diff),axis=0))) if k!='tau' else np.max(abs(diff),axis=0)).tolist()
  lr=[]
  for a,bb in zip(su['learning_records'],sb['learning_records']):
   sa=a['selected_plan']['schedule'];ss=bb['selected_plan']['schedule'];lr.append({'decision_index':a['decision_index'],'phase':sa['phase'],'target_delta_deg':np.degrees(np.array(sa['target_q_rad'])-ss['target_q_rad']).tolist(),'pass_velocity_delta_deg_s':np.degrees(np.array(sa['target_dq_rad_s'])-ss['target_dq_rad_s']).tolist(),'start_q_delta_deg':np.degrees(np.array(sa['start_q_rad'])-ss['start_q_rad']).tolist(),'start_v_delta_deg_s':np.degrees(np.array(sa['start_dq_rad_s'])-ss['start_dq_rad_s']).tolist(),'signed_duration_delta_s':sa['duration_s']-ss['duration_s'],'request_delta_s':a['request_time_s']-bb['request_time_s'],'activated':a['selected_plan_activated']})
  requested_params=r['action'].get('parameters');actual_params=[]
  for a in su['learning_records']:
   for c in a['candidate_set']:
    fm=c['execution_screen'].get('free_trajectory')
    if fm and 'parameters' in fm:actual_params.append(fm['parameters'])
  paramcheck=bool(requested_params is None or actual_params and all(np.max(abs(np.array(z)-requested_params))<1e-12 for z in actual_params))
  # Every applied receipt's torque must own all native rows over (start,end].
  receipts=raw['wall_physics']['command_receipts'];alln=raw['wall_physics']['native_states_evaluation_only'];tn=np.array([n['time_s'] for n in alln]);taun=np.array([n['command_torque_nm'] for n in alln]);bad=[];joined=0
  for rr in receipts:
   if not rr.get('applied'):continue
   lo=np.searchsorted(tn,rr['start_physics_s']+1e-10,side='right');hi=np.searchsorted(tn,rr['end_physics_s']+1e-10,side='right');nn=hi-lo
   if nn!=rr['native_steps'] or not np.all(taun[lo:hi]==rr['command_torque_nm']):bad.append(rr['receipt_index'])
   joined+=nn
  rows.append({'id':ident,'qualified':r['qualified'],'JF':r['JF'],'JM':r['JM'],'difference_vs_best':delta,'reference_layers':lr,'request_reference_count':len(su['learning_records']),'old18d_parameter_identity':paramcheck,'applied_receipt_native_join':{'pass':not bad,'native_rows_joined':joined,'bad_receipts':bad},'motion_vs_B':r['motion_vs_B'],'axes':m['axes'],'clearance':m['clearance'],'native_new_steps':m['actual_new_native_steps'],'parent':m['branch'],'initial_fit_semantic_error':ident=='P1_OLD_FIT'})
  print('COMPARED',ident,'params',paramcheck,'receipt',not bad,flush=True)
 (P/'analysis/PHYSICAL_COMPARISON.json').write_text(json.dumps({'base':'P1_BEST','rows':rows,'same_cold_condition_parent_hashes':sorted(set(r['parent']['full_hash'] for r in rows)),'scope':'Same physical-time interpolation, not phase-optimized alignment. Signed target/pass/duration and issued receipts retained separately. Nonzero torque/Human differences mean no exact physical equivalence; differing JF does not prove unreachable old performance.'},indent=2,default=lambda o:o.item())+'\n')
if __name__=='__main__':main()
