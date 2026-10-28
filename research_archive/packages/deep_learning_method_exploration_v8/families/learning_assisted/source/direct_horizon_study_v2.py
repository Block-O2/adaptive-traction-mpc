"""Finite-horizon supervised outcomes, separately versioned from autoregression."""
from pathlib import Path
import os,json,time,hashlib,signal,resource
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from causal_dynamics_study import fit, pred, features
F=Path(__file__).resolve().parents[1];P=F.parents[1];V=P.parent/'autonomous_learning_smoothness_v7'
started=time.time();signal.alarm(300)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(n,x):(F/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 identity={'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'started_unix':started,'source_sha256':sha(Path(__file__))}
 put('analysis/DIRECT_HORIZON_PROCESS_START.json',identity)
 source=P/'families/critic_value/data/HISTORICAL_RECIPE_DATASET_V2.json';d=json.loads(source.read_text());recipes=sorted({r['action_recipe_sha256'] for r in d['rows']});series=[];hashes={str(source):sha(source)}
 for row in d['rows']:
  f=V/'history'/(row['id']+'_CAUSAL_HISTORY.json')
  if not f.exists() or not row['labels_evaluation_only']['complete']:continue
  h=json.loads(f.read_text());hashes[str(f)]=sha(f)
  s=np.array([r['estimated_q_dq']+r['reference_q_dq']+r['measured_force']+r['measured_moment'] for r in h]);t=np.array([r['time_s'] for r in h]);t-=t[0]
  ph=np.array([['OUTBOUND','HOLD','RETURN'].index(r['phase']) for r in h]);ctx=np.array(row['context']['features'])
  series.append({'id':row['id'],'group':row['group'],'s':s,'t':t,'ph':ph,'ctx':ctx,'action':recipes.index(row['action_recipe_sha256']),'cum':np.column_stack([np.r_[0,np.cumsum(np.linalg.norm(s[:-1,8:11],axis=1)*.005)],np.r_[0,np.cumsum(np.linalg.norm(s[:-1,11:14],axis=1)*.005)]])})
 def design(s,ix):
  return np.column_stack([features(s['s'][ix],s['s'][ix-2],s['t'][ix],s['ph'][ix],s['action'],len(recipes),True),np.repeat(s['ctx'][None],len(ix),axis=0)])
 results=[];solves=0
 for group in sorted({s['group'] for s in series}):
  train=[s for s in series if s['group']!=group];test=[s for s in series if s['group']==group]
  for horizon in [.5,1.,2.]:
   count=round(horizon/.005);xs=[];ys=[]
   for s in train:
    ix=np.unique(np.linspace(2,len(s['s'])-count-1,min(800,len(s['s'])-count-3)).astype(int))
    xs.append(design(s,ix));ys.append(np.column_stack([s['s'][ix+count]-s['s'][ix],s['cum'][ix+count]-s['cum'][ix]]))
   model=fit(np.concatenate(xs),np.concatenate(ys));solves+=1
   for s in test:
    for ix in [2,min(2202,len(s['s'])-count-2)]:
     if ix<2:continue
     actual=np.r_[s['s'][ix+count]-s['s'][ix],s['cum'][ix+count]-s['cum'][ix]]
     pr=pred(model,design(s,np.array([ix])))[0]
     results.append({'group':group,'id':s['id'],'start_post_action_s':float(s['t'][ix]),'horizon_s':horizon,'terminal_error':(pr[:14]-actual[:14]).tolist(),'predicted_window_JF':float(pr[14]),'actual_window_JF':float(actual[14]),'predicted_window_JM':float(pr[15]),'actual_window_JM':float(actual[15]),'persistence_window_JF':float(np.linalg.norm(s['s'][ix,8:11])*horizon),'persistence_window_JM':float(np.linalg.norm(s['s'][ix,11:14])*horizon)})
   print('DIRECT_FOLD',group,horizon,flush=True)
 out={'status':'COMPLETED_DIAGNOSTIC_ONLY','rows':results,'series':len(series),'whole_context_folds':len({s['group'] for s in series}),'ridge_solves':solves,'source_sha256':hashes,'new_physics':0,'new_policy_updates':0,'one_common_preaction_state':False,'wall_s':time.time()-started,'cpu_s':time.process_time(),'max_RSS_KiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 put('analysis/DIRECT_HORIZON_RESULTS_V2.json',out);put('analysis/DIRECT_HORIZON_PROCESS_END.json',{**identity,'ended_unix':time.time(),'status':'PASS_DIAGNOSTIC_ONLY'})
if __name__=='__main__':
 try:main()
 except BaseException as e:put('analysis/DIRECT_HORIZON_PROCESS_FAILURE.json',{'error':str(e),'ended_unix':time.time()});raise
