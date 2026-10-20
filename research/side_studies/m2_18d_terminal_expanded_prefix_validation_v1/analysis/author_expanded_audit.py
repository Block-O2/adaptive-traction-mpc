"""Offline prefix matching and whole-task failure localization; no physics imports."""
from pathlib import Path
import os,json,sys,hashlib,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
L=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/L.name;A=P.parent/'m2_18d_terminal_response_repair_v1'
def read(n):return json.loads((P/n).read_text())
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
protocol=read('MOTION_ACCEPTANCE_PROTOCOL.json')['primary'];out=[]
for g in sys.argv[1:] or ['V1','V2']:
 rr=read(g+'_RESULTS.json');rows=rr['rows'];base=read('reports/'+g+'_B_MEASURED.json');bd=read('output/'+g+'_B_DATA.json');fork=bd['branch_start']['physical_time_s'];checks=read('reports/'+g+'_PARENT_CHECKS.json');assert all(c['unchanged'] and c['child_exitcode']==0 for c in checks)
 assert read(g+'_PAIR_GATE.json')['status']=='PASS' and read(g+'_PARENT_GATE.json')['status']=='PASS'
 histories={};prefix_audits=[];diagnoses=[]
 with np.load(P/'source/results'/(g+'_B')/'trace.npz') as z:
  t0=float(z['time_s'][z['stage']=='TASK'][0]);mask=z['time_s']<=fork+1e-9;pre={k:z[k][mask].copy() for k in z.files if z[k].shape[0]==len(mask)}
  taskmask=(z['time_s']>=t0-1e-9)&(z['time_s']<=fork+1e-9);time=z['time_s'][taskmask];force=np.linalg.norm(z['physical_cuff_force_world_n'][taskmask],axis=1);prefix_jf=float(force[:-1]@np.diff(time));human_at_fork=z['evaluation_only_human_state_rad_rad_s'][np.argmin(abs(z['time_s']-fork))].tolist()
 for r in rows:
  ident=r['id'];data=read('output/'+ident+'_DATA.json');assert data['branch_start']['full_hash']==bd['branch_start']['full_hash'];dec=read('output/'+ident+'_DECISIONS.json')['rows'];prefix=dec[0];assert prefix['legal_shared_prefix'] and prefix['native_index']==0 and prefix['action']==rr['condition']['prefix']['OUTBOUND'][0]
  lineage=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');first=lineage['rows'][0];assert first['activation_outcome']=='ACTIVATED' and first['selected_plan_activated'] and first['actual_native_steps']>0
  receipts=[x for x in first['actual_command_receipts'] if x['start_physics_s']<fork-1e-9];assert receipts and all(x['applied'] if 'applied' in x else True for x in receipts)
  with np.load(P/'source/results'/ident/'trace.npz') as z:
   m=z['time_s']<=fork+1e-9
   assert all(np.array_equal(z[k][m],v,equal_nan=True) if v.dtype.kind in 'fc' else np.array_equal(z[k][m],v) for k,v in pre.items())
  prefix_audits.append(dict(id=ident,restored=read('reports/'+ident+'_FORK_RESTORED.json'),prefix_action=prefix['action'],prefix_decision=prefix,full_pre_fork_trace_fields_exact=len(pre),prefix_native_steps_before_fork=sum(x['native_steps'] for x in receipts),prefix_first_physical_s=receipts[0]['start_physics_s'],prefix_end_physical_s=receipts[-1]['end_physics_s'],consumed_action='OUTBOUND native index 0; remaining validation begins at index 1',task_prefix_J_F_N_s=prefix_jf,full_task_J_F_includes_common_prefix=True,remaining_J_F_N_s=data['remaining_J_F'],branch_J_F_arithmetic_error=data['metric']['J_F']-data['remaining_J_F']-data['child']['start_J_F']))
  assert abs(prefix_audits[-1]['branch_J_F_arithmetic_error'])<1e-8
  cmp=r['motion'];meas=read('reports/'+ident+'_MEASURED.json');details=[]
  with np.load(P/'motion_series'/(ident+'.npz')) as z,np.load(P/'motion_series'/(g+'_B.npz')) as bz:
   nt=z['time_s'];phase=z['phase'];bphase=bz['phase'];signals={'velocity_deg_s':np.rad2deg(z['true_dq_rad_s']),'acceleration_deg_s2':np.rad2deg(z['acceleration_rad_s2']),'jerk_deg_s3':np.rad2deg(z['jerk_rad_s3'])};bsignals={'velocity_deg_s':np.rad2deg(bz['true_dq_rad_s']),'acceleration_deg_s2':np.rad2deg(bz['acceleration_rad_s2']),'jerk_deg_s3':np.rad2deg(bz['jerk_rad_s3'])}
   for req in cmp['failed_requirements']:
    if '/' not in req:details.append(dict(requirement=req,comparison=cmp));continue
    sig,met=req.split('/');av=np.asarray(meas['motion']['raw']['full'][sig][met]);bv=np.asarray(base['motion']['raw']['full'][sig][met])
    for j,joint in enumerate(['hip','knee']):
     if av[j]<=bv[j]*protocol['burden_ratio']+1e-7:continue
     x=signals[sig][:,j];peak=int(np.argmax(abs(x)));byphase={ph:dict(candidate=meas['motion']['raw']['phases'][ph][sig][met][j],B=base['motion']['raw']['phases'][ph][sig][met][j],ratio=meas['motion']['raw']['phases'][ph][sig][met][j]/max(base['motion']['raw']['phases'][ph][sig][met][j],1e-12),above_full_B_limit_time_s=float(np.sum((phase==ph)&(abs(x)>bv[j]*protocol['burden_ratio']))*.00025),mean_square_delta=float(np.sum(x[phase==ph]**2)/len(x)-np.sum(bsignals[sig][bphase==ph,j]**2)/len(bphase))) for ph in ['OUTBOUND','HOLD','RETURN']}
     details.append(dict(requirement=req,joint=joint,ratio=av[j]/bv[j],limit=protocol['burden_ratio'],candidate=av[j],B=bv[j],peak=dict(task_s=nt[peak]-nt[0],phase=str(phase[peak]),signed_value=x[peak]),phase_contributions=byphase,phase_ratios_are_diagnostic_only=True))
   peaks={joint:dict(task_s=float(nt[int(np.argmax(abs(signals['acceleration_deg_s2'][:,j])))]-nt[0]),phase=str(phase[int(np.argmax(abs(signals['acceleration_deg_s2'][:,j])))]),absolute_deg_s2=float(np.max(abs(signals['acceleration_deg_s2'][:,j])))) for j,joint in enumerate(['hip','knee'])}
  diagnoses.append(dict(id=ident,arm=r['arm'],motion_pass=cmp['acceptance_pass'],failed_requirements=cmp['failed_requirements'],failure_details=details,full_acceleration_peaks=peaks,task=r['task'],safety=r['absolute_safety'],receipt=r['receipt']))
 historical_q=[]
 for hg in ['N2','U1']:
  d=json.loads((A/'output'/(hg+'_B_DATA.json')).read_text());f=d['branch_start']['physical_time_s']
  with np.load(A/'source/results'/(hg+'_B')/'trace.npz') as z:q=z['evaluation_only_human_state_rad_rad_s'][np.argmin(abs(z['time_s']-f))]
  diff=np.asarray(human_at_fork)-q;assert np.max(abs(diff))>1e-8;historical_q.append(dict(condition=hg,human_q_dq_difference=diff.tolist(),different_state=True))
 row=dict(condition=g,status='PASS',condition_spec=rr['condition'],full_live_parent_hash=bd['branch_start']['full_hash'],native_hash=bd['branch_start']['native_hash'],fork_physical_s=fork,fork_task_s=fork-t0,human_q_dq_at_fork_evaluation_only=human_at_fork,not_used_by_controller=True,distinct_from_historical=historical_q,prefix=prefix_audits,parent_checks=checks,diagnosis=diagnoses)
 put('audit/'+g+'_PREFIX_AND_FAILURE_AUDIT.json',row);out.append(row);print('PREFIX_DIAGNOSIS',g,[(r['arm'],r['motion_pass'],r['failed_requirements']) for r in diagnoses],flush=True)
if len(out)>1:
 assert len(set(r['native_hash'] for r in out))==len(out)
 assert np.max(abs(np.asarray(out[0]['human_q_dq_at_fork_evaluation_only'])-out[1]['human_q_dq_at_fork_evaluation_only']))>1e-8
put('audit/EXPANDED_PREFIX_AUDIT.json',dict(status='PASS',groups=out,same_Human=True,no_state_replay=True,no_physics_imports=True))
