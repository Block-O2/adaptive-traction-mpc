"""Independent auxiliary evaluation of original native signals; no filtering/scalarization."""
from pathlib import Path
import os,sys,json,time,hashlib,signal
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'runtime/code'),str(P/'runtime/deps'),str(P/'source')]
import numpy as np
from stream_runtime_evidence import array_items
from acl2_shared import put,sha,read

def stats(x):
 x=np.asarray(x);return {'rms':np.sqrt(np.mean(x*x,axis=0)).tolist(),'peak_abs':np.max(abs(x),axis=0).tolist(),'p95_abs':np.quantile(abs(x),.95,axis=0).tolist(),'p99_abs':np.quantile(abs(x),.99,axis=0).tolist()}
def wrench(t,x):
 norm=np.linalg.norm(x,axis=1);rate=np.gradient(x,t,axis=0,edge_order=2);nr=np.gradient(norm,t,edge_order=2)
 return {'vector':stats(x),'norm':stats(norm),'vector_rate':stats(rate),'norm_rate':stats(nr),'vector_rate_RMS':float(np.sqrt(np.mean(np.sum(rate*rate,axis=1)))),'TV_vector':float(np.linalg.norm(np.diff(x,axis=0),axis=1).sum()),'TV_norm':float(abs(np.diff(norm)).sum())}
def evaluate(id):
 row=read('attempts/'+id+'_RESULT.json');assert row['complete']
 dest=P/'analysis/native_metrics'/(id+'.json');raw=P/'runtime/source/results'/id;source_hashes={f:sha(raw/f) for f in ['trace.npz','runtime_artifacts.json.gz','summary.json']}
 if dest.exists():
  old=json.loads(dest.read_text());assert old['source_hashes']==source_hashes,'IMMUTABLE_RAW_CHANGED';return old
 m=read(row['metrics_path']);su=json.loads((raw/'summary.json').read_text());trans={r['to']:r['time_s'] for r in su['task']['phase_transitions']}
 with np.load(raw/'trace.npz') as z:
  ix=z['stage']=='TASK';t=z['time_s'][ix];f=z['physical_cuff_force_world_n'][ix];mom=z['physical_cuff_moment_world_nm'][ix];torque=z['cr12_actuator_command_nm'][ix];q=z['evaluation_only_human_state_rad_rad_s'][ix,:2];ref=z['reference_q_rad'][ix]
  jf=float(np.linalg.norm(f[:-1],axis=1)@np.diff(t));jm=float(np.linalg.norm(mom[:-1],axis=1)@np.diff(t))
 assert abs(jf-row['JF'])<1e-8 and abs(jm-row['JM'])<1e-8,'ORIGINAL_INTEGRAL_MISMATCH'
 times=[];ws=[];vs=[];qs=[];commands=[];qi=m['quality']['qpos_indices'];vi=m['quality']['qvel_indices']
 for n in array_items(raw/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  if t[0]-1e-9<=n['time_s']<=t[-1]+1e-9:
   times.append(n['time_s']);ws.append(n['cuff_wrench_world_evaluation_only']);vs.append([n['qvel_evaluation_only'][i] for i in vi]);qs.append([n['qpos_evaluation_only'][i] for i in qi]);commands.append(n['command_torque_nm'])
 nt=np.asarray(times);w=np.asarray(ws);v=np.asarray(vs);nq=np.asarray(qs);nc=np.asarray(commands);assert np.max(abs(np.diff(nt)-.00025))<1e-9,'NATIVE_GRID'
 acc=np.gradient(v,nt,axis=0,edge_order=2);jerk=np.gradient(acc,nt,axis=0,edge_order=2);motion={name:stats(np.degrees(x)) for name,x in [('velocity_deg_s',v),('acceleration_deg_s2',acc),('jerk_deg_s3',jerk)]}
 jerk_error=float(np.max(abs(np.asarray(motion['jerk_deg_s3']['rms'])-m['motion']['raw']['full']['jerk_deg_s3']['rms'])));assert jerk_error<1e-7,'ORIGINAL_JERK_REBUILD_MISMATCH'
 jj=np.clip(np.searchsorted(nt,t),0,len(nt)-1);left=np.maximum(jj-1,0);jj=np.where(abs(nt[left]-t)<abs(nt[jj]-t),left,jj);hit=abs(nt[jj]-t)<1e-8;fe=float(np.max(abs(w[jj[hit],:3]-f[hit])));me=float(np.max(abs(w[jj[hit],3:]-mom[hit])));assert fe<1e-8 and me<1e-8,'NATIVE_WRENCH_OVERLAP'
 phases={};bounds=[t[0],trans['HOLD'],trans['RETURN'],trans['COMPLETE']]
 for ph,lo,hi in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
  k=(nt>=lo-1e-9)&(nt<=hi+1e-9);phases[ph]={'jerk_RMS_deg_s3':np.sqrt(np.mean(np.degrees(jerk[k])**2,axis=0)).tolist(),'force_norm_rate_RMS_N_s':wrench(nt[k],w[k,:3])['norm_rate']['rms']}
 rejection=[];guard_active=guard_unsatisfied=0;max_guard_correction=0.;attempts=0
 for e in array_items(raw/'runtime_artifacts.json.gz','execution_attempts'):
  if not t[0]-1e-9<=e['source_sample_time_s']<=t[-1]+1e-9:continue
  attempts+=1;g=e.get('clearance_feedback',{})
  if g:
   guard_active+=int(g.get('active',False));guard_unsatisfied+=int(not g.get('constraint_satisfied',True));max_guard_correction=max(max_guard_correction,float(np.linalg.norm(g.get('correction_nm',[0.]))))
 fallback=list(array_items(raw/'runtime_artifacts.json.gz','safe_fallback_events'))
 result={'id':id,'qualified_original':row['qualified'],'JF':jf,'JM':jm,'native_motion':motion,'native_force':wrench(nt,w[:,:3]),'native_moment':wrench(nt,w[:,3:]),'native_samples':len(nt),'native_dt_s':.00025,'phase_metrics':phases,'tracking_RMS_deg':m['tracking_RMS_deg'],'excursion_deg':m['dose']['excursion_deg'],'endpoint_deg':m['dose']['endpoint_deg'],'clearance':m['clearance'],'axes':m['axes'],'original_motion_comparison':row['motion_vs_B'],'native_torque':stats(nc),'trace_torque':stats(torque),'trace_torque_rate':stats(np.gradient(torque,t,axis=0,edge_order=2)),'guard':{'execution_attempts':attempts,'active':guard_active,'unsatisfied':guard_unsatisfied,'peak_correction_Nm':max_guard_correction},'fallback_events':fallback,'modal_rejections':[x for x in row.get('execution',[]) if isinstance(x,dict) and (x.get('modal') or {}).get('status')=='REJECTED'],'original_integral_error':[jf-row['JF'],jm-row['JM']],'original_jerk_RMS_rebuild_max_error':jerk_error,'original_5ms_wrench_overlap_error':[fe,me],'source_hashes':source_hashes,'signals':'Original unfiltered native Human velocity and cached cuff wrench; native truth evaluation only','integration_contract':'Original TASK 5ms measured wrench left sum, including HOLD; no new weighted reward'}
 put('analysis/native_metrics/'+id+'.json',result);print('NATIVE_METRICS',id,'qual',row['qualified'],'JF',jf,'JM',jm,'jerk',motion['jerk_deg_s3']['rms'],'forceRate',result['native_force']['norm_rate']['rms'],flush=True);return result

def compare(group):
 base=P/'analysis/native_metrics'/(group+'_V6PHASE.json')
 if not base.exists():return
 b=json.loads(base.read_text());bounds=read('freeze/'+group+'.json')['quality_contract'];out=[]
 for f in sorted((P/'analysis/native_metrics').glob(group+'_*.json')):
  m=json.loads(f.read_text());ratios=np.r_[np.asarray(m['native_motion']['jerk_deg_s3']['rms'])/b['native_motion']['jerk_deg_s3']['rms'],m['native_force']['norm_rate']['rms']/b['native_force']['norm_rate']['rms']];retain=bool(np.all(ratios<=[bounds['hip_knee_jerk_RMS_ratio_max_vs_V6PHASE']]*2+[bounds['force_norm_rate_RMS_ratio_max_vs_V6PHASE']]))
  out.append({'id':m['id'],'qualified_original':m['qualified_original'],'JF':m['JF'],'JM':m['JM'],'delta_JF_vs_V6PHASE':m['JF']-b['JF'],'delta_JM_vs_V6PHASE':m['JM']-b['JM'],'hip_knee_jerk_force_rate_ratio_vs_V6PHASE':ratios.tolist(),'extra_quality_retained':retain,'both_cost_improvement_and_quality':bool(m['qualified_original'] and b['qualified_original'] and retain and m['JF']<b['JF'] and m['JM']<=b['JM'])})
 put('analysis/'+group+'_PAIRED_METRICS.json',{'group':group,'rows':out,'status':'ONGOING' if not (P/'jobs'/group/'WORKER_DONE.json').exists() else 'COMPLETED','criterion_frozen':bounds,'evaluation_only':True})
 return out
if __name__=='__main__':
 job='METRICS_'+str(time.time_ns());start=time.time();signal.alarm(max(1,int(min(900,read('ACTIVATION.json')['deadline_unix']-start))));identity={'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'started_unix':start,'source_sha256':sha(Path(__file__)),'arguments':sys.argv[1:],'branch':'EVALUATION_AND_RAW_RECOMPUTE'};put('owned/'+job+'_START.json',identity)
 try:
  ids=sys.argv[1:]
  if ids and ids[0]=='--group':
   group=ids[1];ids=[f.name[:-12] for f in sorted((P/'attempts').glob(group+'_*_RESULT.json')) if json.loads(f.read_text()).get('complete')]
  else:group=None
  for id in ids:evaluate(id)
  if group:compare(group)
  put('owned/'+job+'_END.json',dict(status='PASS',ended_unix=time.time(),wall_s=time.time()-start,**identity))
 except BaseException as e:
  put('owned/'+job+'_END.json',dict(status='FAILED_PRESERVED',ended_unix=time.time(),error=str(e),**identity));raise
