"""Read-only raw arithmetic/ownership checker. Never imports runner or plant."""
from pathlib import Path
import os,sys,json,gzip,hashlib,time,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,allow_nan=False,ensure_ascii=False)+'\n')
def array_items(path,key):
 with gzip.open(path,'rt') as f:
  buf='';needle='"'+key+'":';found=False;decoder=json.JSONDecoder()
  while not found:
   part=f.read(65536)
   if not part:raise ValueError('MISSING_ARRAY:'+key)
   buf+=part;pos=buf.find(needle)
   if pos>=0:
    buf=buf[pos+len(needle):].lstrip()
    while not buf:buf+=f.read(65536);buf=buf.lstrip()
    assert buf.startswith('[');buf=buf[1:];found=True
   else:buf=buf[-len(needle):]
  while True:
   buf=buf.lstrip(', \n\r\t')
   if buf.startswith(']'):return
   try:value,end=decoder.raw_decode(buf)
   except json.JSONDecodeError:
    part=f.read(65536)
    if not part:raise ValueError('TRUNCATED_ARRAY:'+key)
    buf+=part;assert len(buf)<4*2**20;continue
   yield value;buf=buf[end:]
def sha(f):
 h=hashlib.sha256()
 with f.open('rb') as z:
  for b in iter(lambda:z.read(2**20),b''):h.update(b)
 return h.hexdigest()
def stats(x):return dict(max_abs=np.max(abs(x),axis=0),p95_abs=np.quantile(abs(x),.95,axis=0),rms=np.sqrt(np.mean(x*x,axis=0)))
def measure(ident):
 folder=P/'source/results'/ident;m=read('reports/'+ident+'_MEASURED.json');su=json.loads((folder/'summary.json').read_text());data=read('output/'+ident+'_DATA.json')
 with np.load(folder/'trace.npz') as z:
  ix=z['stage']=='TASK';t=z['time_s'][ix].copy();force=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);moment=np.linalg.norm(z['physical_cuff_moment_world_nm'][ix],axis=1);truth=z['evaluation_only_human_state_rad_rad_s'][ix].copy();ref=z['reference_q_rad'][ix].copy()
 jf=float(force[:-1]@np.diff(t));mi=float(moment[:-1]@np.diff(t));assert abs(jf-m['J_F_N_s'])<1e-8 and abs(mi-m['moment_integral_Nm_s'])<1e-8
 assert su['task']['phase_transitions'][-1]['to']=='COMPLETE'
 trans={r['to']:r['time_s'] for r in su['task']['phase_transitions']};bounds=[t[0],trans['HOLD'],trans['RETURN'],trans['COMPLETE']];phases={}
 for ph,lo,hi in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
  w=np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo));v=float(force[:-1]@w);mm=float(moment[:-1]@w)
  assert abs(v-m['phase_cost']['phases'][ph]['J_F_N_s'])<1e-8
  assert abs((hi-lo)-m['phase_durations'][ph])<1e-8
  phases[ph]=dict(J_F_N_s=v,moment_integral_Nm_s=mm,integrated_duration_s=float(w.sum()),phase_clock_duration_s=m['phase_durations'][ph])
 assert abs(sum(v['J_F_N_s'] for v in phases.values())-jf)<1e-8
 _,rev=np.unique(t[::-1],return_index=True);unique=np.sort(len(t)-1-rev);tracking=np.rad2deg(np.sqrt(np.mean((truth[unique,:2]-ref[unique])**2,axis=0)))
 assert np.max(abs(tracking-np.asarray(m['tracking_RMS_deg'])))<1e-8
 receipts=list(array_items(folder/'runtime_artifacts.json.gz','command_receipts'));positive=sorted([r for r in receipts if r.get('applied') and r.get('native_steps',0)>0],key=lambda r:r['start_physics_s'])
 assert positive and all(abs(a['end_physics_s']-b['start_physics_s'])<1e-8 for a,b in zip(positive,positive[1:]))
 counter=collections.Counter();nt=[];qp=[];vp=[];index=0;native=0;age=[]
 for row in array_items(folder/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  begin=row.get('physical_interval_start_s',row['time_s']-.00025)
  while index+1<len(positive) and begin>=positive[index]['end_physics_s']-1e-9:index+=1
  r=positive[index];assert r['start_physics_s']-1e-8<=begin<r['end_physics_s']+1e-8
  assert row['command_torque_nm']==r['command_torque_nm'];cid=row.get('command_id')
  if cid is not None:assert cid==r['receipt_index']
  counter[r['receipt_index']]+=1;native+=1
  if t[0]-1e-9<=row['time_s']<=t[-1]+1e-9:
   nt.append(row['time_s']);qp.append(row['qpos_evaluation_only']);vp.append(row['qvel_evaluation_only'])
 for r in positive:assert counter[r['receipt_index']]==r['native_steps']
 for r in receipts:
  if r.get('applied') and r.get('apply_ns') is not None and r.get('sensor_age_at_apply_ms') is not None:
   assert r['sensor_age_at_apply_ms']<=100+1e-7;age.append(r['sensor_age_at_apply_ms'])
 nt=np.asarray(nt);qp=np.asarray(qp);vp=np.asarray(vp);assert np.max(abs(np.diff(nt)-.00025))<1e-10
 # Infer Human coordinate columns directly from trace/native common times.
 sel=np.clip(np.searchsorted(nt,t),0,len(nt)-1);left=np.maximum(sel-1,0);sel=np.where(abs(nt[left]-t)<abs(nt[sel]-t),left,sel);close=abs(nt[sel]-t)<1e-8
 eq=np.max(abs(qp[sel[close],:,None]-truth[close,None,:2]),axis=0);ev=np.max(abs(vp[sel[close],:,None]-truth[close,None,2:]),axis=0);qi=np.argmin(eq,axis=0);vi=np.argmin(ev,axis=0)
 assert max(eq[qi,np.arange(2)].max(),ev[vi,np.arange(2)].max())<1e-8
 q=qp[:,qi];v=vp[:,vi];a=np.gradient(v,nt,axis=0,edge_order=2);j=np.gradient(a,nt,axis=0,edge_order=2)
 phase=np.full(len(nt),'OUTBOUND',dtype='<U10')
 for ph in ['HOLD','RETURN']:phase[nt>=trans[ph]-1e-9]=ph
 for name,x in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',j)]:
  for met,value in stats(np.rad2deg(x)).items():assert np.max(abs(value-np.asarray(m['motion']['raw']['full'][name][met])))<1e-8
  for ph in ['OUTBOUND','HOLD','RETURN']:
   for met,value in stats(np.rad2deg(x[phase==ph])).items():assert np.max(abs(value-np.asarray(m['motion']['raw']['phases'][ph][name][met])))<1e-8
 dose=dict(excursion_deg=np.rad2deg(np.ptp(q,axis=0)),cumulative_travel_deg=np.rad2deg(np.sum(abs(np.diff(q,axis=0)),axis=0)),endpoint_deg=np.rad2deg(q[-1]))
 for k,x in dose.items():assert np.max(abs(x-np.asarray(m['dose'][k])))<1e-8
 assert abs((nt[-1]-nt[0])-m['dose']['duration_s'])<1e-8
 for ph in ['OUTBOUND','HOLD','RETURN']:
  sub=q[phase==ph]
  for k,x in [('start_deg',sub[0]),('end_deg',sub[-1])]:assert np.max(abs(np.rad2deg(x)-np.asarray(m['dose']['phase_boundaries'][ph][k])))<1e-8
 with np.load(P/'motion_series'/(ident+'.npz')) as z:
  assert np.array_equal(z['time_s'],nt) and np.array_equal(z['true_q_rad'],q) and np.array_equal(z['true_dq_rad_s'],v)
  assert np.array_equal(z['acceleration_rad_s2'],a) and np.array_equal(z['jerk_rad_s3'],j)
 assert all(sha(Path(f))==h for f,h in m['sources'].items())
 result=dict(id=ident,status='PASS',evidence='CURRENT_RAW_RECOMPUTATION',J_F_N_s=jf,moment_integral_Nm_s=mi,complete_task_duration_s=float(t[-1]-t[0]),phase=phases,tracking_RMS_deg=tracking,native_rows=native,receipt_count=len(receipts),ownership='every native row uniquely joined by contiguous positive receipt interval, exact torque and step count; direct command_id checked if present',source_age_max_ms=max(age,default=None),actual_new_native_steps=data['metric']['actual_new_native_physics_steps'],raw_hashes_verified=True,human_mapping=dict(qpos=qi,qvel=vi),motion_recomputed_from_native=True,full_and_phase_motion_statistics_verified=True,dose_and_boundaries_verified=True)
 put('derived/'+ident+'_INDEPENDENT.json',result);print('RAW_RECOMPUTED',ident,jf,flush=True);return clean(result)
def diagnose(group):
 a=read('reports/'+group+'_E_MEASURED.json');b=read('reports/'+group+'_B_MEASURED.json');cmp=read(group+'_RESULTS.json')['rows'][1]['motion'];protocol=read('MOTION_ACCEPTANCE_PROTOCOL.json')['primary'];details=[]
 with np.load(P/'motion_series'/(group+'_B.npz')) as bz:
  bphase=bz['phase'].copy();bsignals={'velocity_deg_s':np.rad2deg(bz['true_dq_rad_s']),'acceleration_deg_s2':np.rad2deg(bz['acceleration_rad_s2']),'jerk_deg_s3':np.rad2deg(bz['jerk_rad_s3'])}
 with np.load(P/'motion_series'/(group+'_E.npz')) as z:
  nt=z['time_s'];phase=z['phase'];signals={'velocity_deg_s':np.rad2deg(z['true_dq_rad_s']),'acceleration_deg_s2':np.rad2deg(z['acceleration_rad_s2']),'jerk_deg_s3':np.rad2deg(z['jerk_rad_s3'])}
  for req in cmp['failed_requirements']:
   if '/' in req:
    sig,met=req.split('/');av=np.asarray(a['motion']['raw']['full'][sig][met]);bv=np.asarray(b['motion']['raw']['full'][sig][met])
    for idx,joint in enumerate(['hip','knee']):
     if av[idx]<=bv[idx]*protocol['burden_ratio']+1e-7:continue
     x=signals[sig][:,idx];peak=int(np.argmax(abs(x)));byph={ph:dict(candidate=a['motion']['raw']['phases'][ph][sig][met][idx],B=b['motion']['raw']['phases'][ph][sig][met][idx],ratio=a['motion']['raw']['phases'][ph][sig][met][idx]/max(b['motion']['raw']['phases'][ph][sig][met][idx],1e-12)) for ph in ['OUTBOUND','HOLD','RETURN']}
     tail={ph:dict(samples=int(np.sum((phase==ph)&(abs(x)>bv[idx]*protocol['burden_ratio']))),duration_s=float(np.sum((phase==ph)&(abs(x)>bv[idx]*protocol['burden_ratio']))*.00025)) for ph in ['OUTBOUND','HOLD','RETURN']}
     mean_square={ph:float(np.sum(x[phase==ph]**2)/len(x)-np.sum(bsignals[sig][bphase==ph,idx]**2)/len(bphase)) for ph in ['OUTBOUND','HOLD','RETURN']}
     dominant=str(phase[peak]) if met=='max_abs' else max(tail,key=lambda ph:tail[ph]['samples']) if met=='p95_abs' else max(mean_square,key=mean_square.get)
     details.append(dict(requirement=req,joint=joint,full_ratio=av[idx]/bv[idx],full_limit=protocol['burden_ratio'],phase_diagnostics=byph,above_full_B_metric_limit_by_phase=tail,mean_square_delta_contribution_by_phase=mean_square,dominant_diagnostic_phase=dominant,phase_attribution_rule='max uses actual peak; p95 uses count exceeding the full B metric limit; RMS uses change in full-normalized mean-square contribution',absolute_peak=dict(phase=str(phase[peak]),task_s=float(nt[peak]-nt[0]),value=float(x[peak])),phase_ratios_are_diagnostic_not_new_gates=True))
   else:details.append(dict(requirement=req,comparison_evidence=cmp))
 out=dict(condition=group,motion_pass=cmp['acceptance_pass'],failed_requirements=cmp['failed_requirements'],details=details,interpretation='p95/RMS are whole-task statistics; phase contributions localize changes but do not establish a unique causal mechanism')
 put('derived/'+group+'_FAILURE_DIAGNOSIS.json',out);return out
def main():
 groups=sys.argv[1:] or ['reproduction'];out=[]
 for g in groups:
  assert read(g+'_DONE.json')['all_children_joined']
  checks=[measure(g+'_parent')]+[measure(r['id']) for r in read(g+'_RESULTS.json')['rows']]
  assert read(g+'_PAIR_GATE.json')['status']=='PASS'
  out.append(dict(group=g,checks=checks,diagnosis=diagnose(g)))
 forbidden=[n for n in sys.modules if 'mujoco' in n or 'planner' in n or n in ['study_common','campaign','sac_env','runner']];assert not forbidden
 put('audit/INDEPENDENT_'+('_'.join(groups))+'.json',dict(status='PASS',unix=time.time(),checks=out,imports_physics_or_controller=False,method='separate arithmetic script, not independent human/agent audit',new_physical_starts=0))
if __name__=='__main__':main()
