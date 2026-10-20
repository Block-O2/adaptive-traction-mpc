"""Independent saved-evidence analysis; never imports a physics runtime."""
from pathlib import Path
import os,json,hashlib,collections,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
from scipy.signal import find_peaks,savgol_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from evidence import array_items
P=Path(__file__).resolve().parents[1]
IDS=['development_repair2_B0_original','development_repair2_quality_NATIVE_SCALAR_18_063','development_repair2_repair_C2_pair_1_2_116']
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def cum(x,t):return np.r_[0,np.cumsum((x[:-1]+x[1:])/2*np.diff(t))]
def left(x,t):return np.r_[0,np.cumsum(x[:-1]*np.diff(t))]
def statistics(x):return dict(max_abs=np.max(abs(x),axis=0),p95_abs=np.quantile(abs(x),.95,axis=0),rms=np.sqrt(np.mean(x*x,axis=0)))
def analyze(ident):
 f=P/'key_traces'/ident;s=json.loads((f/'summary.json').read_text());old=json.loads((P/'key_traces'/(ident+'_MEASURED.json')).read_text())
 with np.load(f/'trace.npz') as z:
  mask=z['stage']=='TASK';t=z['time_s'][mask].copy();q=z['reference_q_rad'][mask].copy();v=z['reference_dq_rad_s'][mask].copy();a=z['reference_ddq_rad_s2'][mask].copy();truth=z['evaluation_only_human_state_rad_rad_s'][mask].copy();F=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);M=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1);phase=z['task_phase'][mask].copy()
  step=int(z['physics_steps'][-1]);native_dt=s['timing']['physics_dt_s']
 origin=t[0];t=t-origin;I=left(F,t);IM=left(M,t)
 with np.load(P/'key_traces'/(ident+'.npz')) as z:
  nt=z['time_s'].copy()-origin;nq=z['true_q_rad'].copy();nv=z['true_dq_rad_s'].copy();na=np.gradient(nv,nt,axis=0,edge_order=2);nj=np.gradient(na,nt,axis=0,edge_order=2);nph=z['phase'].copy()
  derivative_errors=dict(acceleration=float(np.max(abs(na-z['acceleration_rad_s2']))),jerk=float(np.max(abs(nj-z['jerk_rad_s3']))))
 assert derivative_errors['acceleration']<1e-6 and derivative_errors['jerk']<.01
 assert np.max(abs(np.diff(nt)-.00025))<1e-10
 for name,x in [('velocity_deg_s',nv),('acceleration_deg_s2',na),('jerk_deg_s3',nj)]:
  for key,value in statistics(np.rad2deg(x)).items():assert np.max(abs(value-np.asarray(old['motion']['raw']['full'][name][key])))<(.001 if name.startswith('jerk') else 1e-6)
 assert abs(I[-1]-old['J_F_N_s'])<1e-8
 assert abs(IM[-1]-old['moment_integral_Nm_s'])<1e-8
 bounds=[0]+[x['time_s']-origin for x in s['task']['phase_transitions'] if x['to'] in ['HOLD','RETURN','COMPLETE']]
 cost={}
 for ph,lo,hi in zip(['OUTBOUND','HOLD','RETURN'],bounds,bounds[1:]):
  d=np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo));cost[ph]=dict(J_F_N_s=float(F[:-1]@d),moment_Nm_s=float(M[:-1]@d),duration_s=float(d.sum()))
 assert abs(sum(x['J_F_N_s'] for x in cost.values())-I[-1])<1e-8
 requests=list(array_items(f/'runtime_artifacts.json.gz','requests'));receipts=[r for r in array_items(f/'runtime_artifacts.json.gz','command_receipts') if r.get('applied') and r.get('native_steps',0)>0];events=list(array_items(f/'runtime_artifacts.json.gz','rolling_splice_events'))
 starts=np.array([r['start_physics_s'] for r in receipts]);ends=np.array([r['end_physics_s'] for r in receipts]);assert np.max(abs(starts[1:]-ends[:-1]))<1e-8
 counts=np.zeros(len(receipts),int);ownership_errors=[];native_count=0;native_q=[];native_v=[];native_t=[]
 for row in array_items(f/'runtime_artifacts.json.gz','native_states_evaluation_only'):
  native_count+=1;begin=row['time_s']-native_dt;i=int(np.searchsorted(starts,begin+1e-9,side='right')-1)
  if i<0 or begin>=ends[i]-1e-9 or not np.array_equal(row['command_torque_nm'],receipts[i]['command_torque_nm']):ownership_errors.append(row['time_s'])
  else:counts[i]+=1
  if origin-1e-9<=row['time_s']<=origin+t[-1]+1e-9:
   native_t.append(row['time_s']-origin);native_q.append(row['qpos_evaluation_only'][:2]);native_v.append(row['qvel_evaluation_only'][:2])
 assert not ownership_errors and np.array_equal(counts,[r['native_steps'] for r in receipts]) and native_count==step
 assert np.array_equal(np.asarray(native_q),nq) and np.array_equal(np.asarray(native_v),nv)
 c2=np.array([np.r_[d['reference_boundary_continuity']['q_boundary_jump_rad'],d['reference_boundary_continuity']['dq_boundary_jump_rad_s'],d['reference_boundary_continuity']['ddq_boundary_jump_rad_s2']] for d in s['decisions']])
 task_requests=[r for r in requests if r['stage']=='TASK'];dv=truth[:,2:]-v
 ref_jerk=np.gradient(a,t,axis=0,edge_order=2)
 peaks={}
 for ph in ['OUTBOUND','RETURN']:
  j=np.flatnonzero(phase==ph);peaks[ph]=[]
  for k in range(2):
   # 0.5 deg/s prominence, >=100 ms between extrema; declared diagnostic.
   speed=np.rad2deg(abs(v[j,k]));up,_=find_peaks(speed,prominence=.5,distance=20);down,_=find_peaks(-speed,prominence=.5,distance=20)
   peaks[ph].append(dict(joint=['hip','knee'][k],reference_speed_peaks_task_s=t[j[up]],reference_speed_troughs_task_s=t[j[down]]))
 lag={}
 for ph in ['OUTBOUND','RETURN']:
  j=np.flatnonzero(phase==ph);lag[ph]=[]
  for k in range(2):
   pairs=[]
   for shift in range(-30,31):
    x=v[j,k];y=truth[j,2+k]
    if shift>0:x,y=x[:-shift],y[shift:]
    elif shift<0:x,y=x[-shift:],y[:shift]
    pairs.append((float(np.corrcoef(x,y)[0,1]),shift*.005))
   corr,l=max(pairs);lag[ph].append(dict(joint=['hip','knee'][k],best_lag_s=l,correlation=corr,classification='CORRELATIONAL',range_s=[-.15,.15]))
 error_peaks=[]
 for k in range(2):
  i=np.argmax(abs(dv[:,k]));recent=[e for e in events if e.get('actual_splice_physics_s',float('inf'))<=t[i]+origin];last=max([e['actual_splice_physics_s'] for e in recent],default=None)
  error_peaks.append(dict(joint=['hip','knee'][k],task_s=t[i],error_deg_s=np.rad2deg(dv[i,k]),after_previous_splice_s=None if last is None else t[i]+origin-last))
 tvv=cum(np.sum(abs(na),axis=1),nt);tva=cum(np.sum(abs(nj),axis=1),nt);rtvv=cum(np.sum(abs(a),axis=1),t);rtva=cum(np.sum(abs(ref_jerk),axis=1),t)
 sensitivity={}
 for w in [5,21]:
  vv=savgol_filter(nv,w,3,axis=0,mode='interp');aa=np.gradient(vv,nt,axis=0,edge_order=2);jj=np.gradient(aa,nt,axis=0,edge_order=2)
  sensitivity['SG'+str(w)]=dict(jerk_peak_deg_s3=np.rad2deg(abs(jj)).max(axis=0),TV_v_rad_s=float(cum(np.sum(abs(aa),axis=1),nt)[-1]),TV_a_rad_s2=float(cum(np.sum(abs(jj),axis=1),nt)[-1]))
 out=dict(id=ident,evidence='TRACE_VERIFIED',rollout_origin='historical raw, independently recomputed; no new physics',J_F_N_s=I[-1],moment_integral_Nm_s=IM[-1],duration_s=t[-1],phase=cost,phase_closure_error_N_s=sum(x['J_F_N_s'] for x in cost.values())-I[-1],counts=dict(task_requests=len(task_requests),all_session_requests=len(requests),task_activated=sum(d['plan_activated'] for d in s['decisions']),actual_suffix_splices=sum(e['outcome']=='SPLICED' for e in events),all_session_positive_receipts=len(receipts),all_session_native_steps=native_count,task_native_samples=len(nt),task_native_intervals=len(nt)-1,candidate_counts=[d['candidate_count'] for d in s['decisions']],feasible_candidate_counts=[d['feasible_candidate_count'] for d in s['decisions']]),ownership=dict(status='PASS',join='unique contiguous receipt interval plus exact applied torque and native-step count',errors=ownership_errors),c2_max_jump=np.max(abs(c2),axis=0),TV_v_actual_rad_s=tvv[-1],TV_a_actual_rad_s2=tva[-1],TV_v_reference_rad_s=rtvv[-1],TV_a_reference_rad_s2=rtva[-1],reference_jerk_method='gradient of sampled analytic ddq at 5 ms; transition/hold one-sided behavior included, diagnostic only',derivative_method=dict(actual='np.gradient(raw native dq,t,axis=0,edge_order=2), repeated for jerk',dt_s=.00025,units='rad/s2 and rad/s3; plotted degrees',boundary='second-order one-sided, no endpoints removed',saved_derivative_max_difference=derivative_errors,sensitivity=sensitivity),speed_extrema=peaks,tracking_lag=lag,tracking_error_peaks=error_peaks,events=dict(requests=[dict(id=r['request_id'],task_s=r['source_sample_time_s']-origin,outcome=r['outcome']) for r in task_requests],activations=[dict(id=d['timing_request_id'],task_s=d['activation_timestamp_s']-origin) for d in s['decisions'] if d['plan_activated']],splices=[dict(id=e['request_id'],task_s=e['actual_splice_physics_s']-origin) for e in events if e['outcome']=='SPLICED']),original_motion=old['motion']['raw']['full'],historical_motion_comparison='independently recomputed statistics match archived metrics',full_raw_sha256=sha(f/'runtime_artifacts.json.gz'))
 put('audit/'+ident+'_RECOMPUTED.json',out)
 np.savez_compressed(P/'audit'/(ident+'_diagnostic.npz'),t=t,F=F,M=M,I=I,q=q,v=v,a=a,truth=truth,nt=nt,nq=nq,nv=nv,na=na,nj=nj,tvv=tvv,tva=tva,rtvv=rtvv,rtva=rtva,phase=phase)
 print(json.dumps(clean(dict(id=ident,J_F=I[-1],duration=t[-1],counts=out['counts'],TV_v=tvv[-1],TV_a=tva[-1])),allow_nan=False),flush=True)
 return out

def main():
 rows=[analyze(x) for x in IDS];arrays=[dict(np.load(P/'audit'/(x+'_diagnostic.npz'))) for x in IDS]
 b,c=arrays[:2];assert np.max(abs(b['t']-c['t']))<1e-8
 intervals=[]
 bounds=sorted(set([0,1,2,3,4,5,6,7,8,9.005,10.025,11,12,13,14,15,16,17,18,19.03]))
 for lo,hi in zip(bounds,bounds[1:]):
  def integ(z,key):return np.interp(hi,z['t'],z[key])-np.interp(lo,z['t'],z[key])
  def tv(z,key):return np.interp(hi,z['nt'],z[key])-np.interp(lo,z['nt'],z[key])
  intervals.append(dict(start_s=lo,end_s=hi,gain_N_s=integ(b,'I')-integ(c,'I'),B_mean_force_N=integ(b,'I')/(hi-lo),best_mean_force_N=integ(c,'I')/(hi-lo),B_actual_TV_v=tv(b,'tvv'),best_actual_TV_v=tv(c,'tvv'),B_actual_TV_a=tv(b,'tva'),best_actual_TV_a=tv(c,'tva')))
 put('DIAGNOSTIC_RESULTS.json',dict(status='PASS',physical_starts=0,evidence='TRACE_VERIFIED',runs=rows,intervals=intervals,force_gain_N_s=rows[0]['J_F_N_s']-rows[1]['J_F_N_s'],force_gain_percent=100*(1-rows[1]['J_F_N_s']/rows[0]['J_F_N_s']),phase_gain_N_s={ph:rows[0]['phase'][ph]['J_F_N_s']-rows[1]['phase'][ph]['J_F_N_s'] for ph in rows[0]['phase']},causal_conclusion='No causal decomposition from time correlation; no intervention in this analysis',ranking_scope='historical complete development pair, one exposed Human',duration_comparison='same complete TASK duration and actual phase boundaries',bins=intervals))
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
 fig,ax=plt.subplots(3,1,figsize=(12,9),sharex=True)
 for z,label,col in zip(arrays[:2],['B','18D frozen development best'],['#243b53','#d95f02']):
  ax[0].plot(z['t'],z['F'],label=label,color=col);ax[1].plot(z['t'],z['I'],label=label,color=col);ax[2].plot(z['t'],z['M'],label=label,color=col)
 ax[0].set_ylabel('Cuff force (N)');ax[1].set_ylabel('I_F (N s), original left sum');ax[2].set_ylabel('Cuff moment (N m)');ax[2].set_xlabel('TASK simulation time (s)');ax[0].legend();fig.suptitle('Historical full physical records; independent recomputation, no new rollout')
 for a in ax:
  for t in [9.005,10.025]:a.axvline(t,color='.6',ls='--',lw=.8)
  a.grid(alpha=.2)
 fig.tight_layout();fig.savefig(P/'figures/cumulative_force_motion.png',dpi=160);plt.close(fig)
 fig,ax=plt.subplots(3,1,figsize=(12,9),sharex=True)
 for z,label,col in zip(arrays[:2],['B','18D'],['#243b53','#d95f02']):
  ax[0].plot(z['nt'],np.rad2deg(z['tvv']),label=label+' actual',color=col);ax[0].plot(z['t'],np.rad2deg(z['rtvv']),label=label+' reference',color=col,ls='--')
  ax[1].plot(z['nt'],np.rad2deg(z['tva']),label=label,color=col)
 ax[2].plot(b['t'],b['I']-c['I'],color='#00796b');ax[0].set_ylabel('TV_v (deg/s)');ax[1].set_ylabel('Actual TV_a (deg/s2)');ax[2].set_ylabel('I_B - I_18D (N s)');ax[2].set_xlabel('TASK simulation time (s)');ax[0].legend(ncol=2)
 for a in ax:a.grid(alpha=.2)
 fig.suptitle('Aligned motion variation and force benefit; correlation is not causation');fig.tight_layout();fig.savefig(P/'figures/force_benefit_vs_velocity_variation.png',dpi=160);plt.close(fig)
 fig,ax=plt.subplots(4,1,figsize=(13,10),sharex=True,gridspec_kw={'height_ratios':[2,2,1,1]})
 for z,label,col in zip(arrays[:2],['B','18D'],['#243b53','#d95f02']):
  for k in [0,1]:
   ax[k].plot(z['nt'],np.rad2deg(z['nv'][:,k]),label=label+' actual',color=col,alpha=.85);ax[k].plot(z['t'],np.rad2deg(z['v'][:,k]),label=label+' reference',color=col,ls='--')
 for i,row in enumerate(rows[:2]):
  for k,key in enumerate(['requests','activations','splices']):
   times=[x['task_s'] for x in row['events'][key]];ax[2+i].scatter(times,np.full(len(times),k),marker=['|','o','x'][k],label=key)
  ax[2+i].set_yticks([0,1,2],['request','activate','splice']);ax[2+i].set_ylabel(['B','18D'][i])
 ax[0].set_ylabel('Hip speed (deg/s)');ax[1].set_ylabel('Knee speed (deg/s)');ax[0].legend(ncol=4);ax[-1].set_xlabel('TASK simulation time (s)')
 for a in ax:
  for t in [9.005,10.025]:a.axvline(t,color='.6',ls=':',lw=.8)
  a.grid(alpha=.2)
 fig.tight_layout();fig.savefig(P/'figures/reference_actual_and_events.png',dpi=160);plt.close(fig)
 print('DIAGNOSTIC_COMPLETE',flush=True)
if __name__=='__main__':main()
