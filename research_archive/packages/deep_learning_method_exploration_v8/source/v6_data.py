"""Raw labels and causally truncated input extraction. No training/test mixing."""
from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'runtime/code'));sys.path.insert(0,str(P/'runtime/deps'))
from stream_runtime_evidence import array_items
from v6_observed_history import arrays as observed_history_arrays,with_guards
def put(n,x):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def integral(t,x,lo,hi):return float(np.linalg.norm(x[:-1],axis=1)@np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo)))
def local_risk_features(history,at):
 h=[r for r in history if r['time_s']<=at+1e-9];t=np.array([r['time_s'] for r in h]);x=np.array([r['estimated_q_dq'] for r in h]);keep=np.r_[True,np.diff(t)>1e-10];t,x=t[keep],x[keep]
 a=np.diff(x[:,2:],axis=0)/np.diff(t)[:,None];j=np.diff(a,axis=0)/np.diff(t)[1:,None]
 return np.r_[np.max(abs(x[:,2:]),0),np.max(abs(a),0),np.max(abs(j),0),np.ptp(x[:,:2],0)].tolist()
def group(g,wrench=False):
 c=json.loads((P/'experiments'/f'{g}.json').read_text());out=[]
 for act in c['actions']:
  ident=g+'_'+act['tag'];rf=P/'attempts'/f'{ident}_RESULT.json'
  if not rf.exists():continue
  r=json.loads(rf.read_text());cf=P/'history'/f'{ident}_TAIL_CAUSAL.json'
  if not r['complete'] or not cf.exists():continue
  cap=json.loads(cf.read_text());fork=cap['fork_physical_s'];m=json.loads((P/r['metrics_path']).read_text());ch=json.loads((P/'history'/f'{ident}_CAUSAL_HISTORY.json').read_text())
  with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
   use=z['stage']=='TASK';t=z['time_s'][use];f=z['physical_cuff_force_world_n'][use];mom=z['physical_cuff_moment_world_nm'][use];est=z['estimated_human_state_rad_rad_s'][use]
  guard_events=list(array_items(P/'runtime/source/results'/ident/'runtime_artifacts.json.gz','execution_attempts'));fallback_events=list(array_items(P/'runtime/source/results'/ident/'runtime_artifacts.json.gz','safe_fallback_events'))
  fulljf=integral(t,f,fork,t[-1]);fulljm=integral(t,mom,fork,t[-1]);assert abs(integral(t,f,t[0],t[-1])-r['JF'])<1e-7
  with np.load(P/'runtime/motion_series'/f'{ident}.npz') as z:
   nt=z['time_s'];rem=nt>=fork-1e-9;jerk=np.rad2deg(z['jerk_rad_s3']);jr=np.sqrt(np.mean(jerk[rem]**2,axis=0)).tolist()
   if (P/'runtime/reports'/f'{g}_B_MEASURED.json').exists():
    b=json.loads((P/'runtime/reports'/f'{g}_B_MEASURED.json').read_text());early={}
    for h,feat in cap['captures'].items():
     ix=nt<=feat['physical_s']-.001;rat=[]
     for sig,key in [('velocity_deg_s','true_dq_rad_s'),('acceleration_deg_s2','acceleration_rad_s2')]:rat.extend((np.max(abs(np.rad2deg(z[key][ix])),axis=0)/(1.1*np.array(b['motion']['raw']['full'][sig]['max_abs']))).tolist())
     early[h]=float(max(rat))
  qualmetrics={'full_JF':r['JF'],'full_JM':r['JM'],'full_jerk_RMS_deg_s3':m['motion']['raw']['full']['jerk_deg_s3']['rms'],'remaining_jerk_RMS_deg_s3':jr,'full_motion_worst_ratio':r['worst_ratio'],'failed_requirements':r['motion_vs_B']['failed_requirements'],'axes':r['axes'],'native_steps':r['actual_new_native_steps'],'attempt_wall_s':r['wall_s'],'tracking_RMS_deg':r['tracking']}
  if wrench:
   tw=[];ws=[]
   for n in array_items(P/'runtime/source/results'/ident/'runtime_artifacts.json.gz','native_states_evaluation_only'):
    if t[0]-1e-9<=n['time_s']<=t[-1]+1e-9:tw.append(n['time_s']);ws.append(n['cuff_wrench_world_evaluation_only'])
   tw=np.array(tw);ws=np.array(ws);fn=np.linalg.norm(ws[:,:3],axis=1);mn=np.linalg.norm(ws[:,3:],axis=1);dt=np.diff(tw);der=np.gradient(fn,tw,edge_order=2);md=np.gradient(mn,tw,edge_order=2)
   qualmetrics['wrench']={'native_dt_s':float(np.median(dt)),'derivative_definition':'original v5 np.gradient on native grid, edge_order=2, all endpoints retained','force_norm_rate_RMS_N_s':float(np.sqrt(np.mean(der**2))),'force_vector_rate_RMS_N_s':float(np.sqrt(np.mean(np.sum(np.gradient(ws[:,:3],tw,axis=0,edge_order=2)**2,axis=1)))),'moment_norm_rate_RMS_Nm_s':float(np.sqrt(np.mean(md**2))),'force_peak_N':float(fn.max()),'force_RMS_N':float(np.sqrt(np.mean(fn**2))),'remaining_force_norm_rate_RMS_N_s':float(np.sqrt(np.mean(der[tw>=fork]**2)))}
   jj=np.clip(np.searchsorted(tw,t),0,len(tw)-1);jj=np.where(abs(tw[np.maximum(jj-1,0)]-t)<abs(tw[jj]-t),np.maximum(jj-1,0),jj);match=abs(tw[jj]-t)<1e-8
   err=float(np.max(abs(ws[jj[match],:3]-f[match])));assert err<1e-8,'WRENCH_OVERLAP';qualmetrics['wrench']['original_5ms_overlap_error_N']=err
  for h,feat in cap['captures'].items():
   split=feat['physical_s'];short=integral(t,f,fork,split);tail=integral(t,f,split,t[-1]);assert abs(short+tail-fulljf)<1e-7
   names=feat['feature_names']+['causal_upstream_COMPOSE_0'];values=feat['features']+[float(c.get('upstream_policy')=='COMPOSE' and act['tag']!='B')]
   out.append({'id':ident,'tag':act['tag'],'group':g,'phase':feat['phase'],'parent_hash':cap['fork_parent_hash'],'qualified':r['qualified'],'complete':True,'horizon_s':float(h),'feature_names':names,'features':values,'history_risk_features':with_guards(observed_history_arrays(t,est,f,mom,split,feat['phase']),guard_events,fallback_events,float(t[0]),split),'local_risk_features':local_risk_features(ch,split),'causal_physical_s':split,'continuation_policy':cap['continuation_policy'],'labels':{'short_JF':short,'tail_JF':tail,'full_remaining_JF':fulljf,'short_JM':integral(t,mom,fork,split),'tail_JM':integral(t,mom,split,t[-1]),'full_remaining_JM':fulljm,'remaining_time_s':float(t[-1]-split),'native_peak_ratio_already_by_H_evaluation_only':early[h]},'metrics':qualmetrics,'future_truth_used_in_features':False})
 put('data/'+g+'.json',out);return out
if __name__=='__main__':
 for g in sys.argv[1:]:
  r=group(g,wrench=True);r=[x for x in r if x['tag']!='B' and x['horizon_s']==.5];one=[x for x in json.loads((P/'data'/f'{g}.json').read_text()) if x['tag']!='B' and x['horizon_s']==1.]
  if r:
   choices={'half':min(r,key=lambda x:x['labels']['short_JF'])['tag'],'one':min(one,key=lambda x:x['labels']['short_JF'])['tag'],'full_qualified':min([x for x in r if x['qualified']],key=lambda x:x['labels']['full_remaining_JF'])['tag'] if any(x['qualified'] for x in r) else None}
   print(g,'rows',len(r),'choices',choices,flush=True)
