"""Equal true-physics-budget pattern search vs small GP BO, isolated arm feedback."""
import copy,json,math,time
from pathlib import Path
import numpy as np
from scipy.special import ndtr
from acl2_shared import P,put,utc
from optim_metrics_v1 import evaluate

def objective(row,baseline):
 if not row.get('complete'):return 20.,None
 d=evaluate(row['id'])
 if not row['qualified']:return 5.+min(10.,max(0.,row.get('worst_ratio',1.)-1.)),d
 jerk=np.linalg.norm(d['native_motion']['jerk_deg_s3']['rms'])/np.linalg.norm(baseline['native_motion']['jerk_deg_s3']['rms'])
 force=d['wrench']['force']['norm_rate']['rms']/baseline['wrench']['force']['norm_rate']['rms']
 score=.65*jerk+.35*force+.004*(d['JF']-baseline['JF'])+.004*(d['JM']-baseline['JM'])
 return float(score),d

def gp_predict(X,y,T):
 X=np.asarray(X);y=np.asarray(y);T=np.asarray(T);l=.7
 def kernel(a,b):return np.exp(-.5*np.sum(((a[:,None,:]-b[None,:,:])/l)**2,axis=2))
 K=kernel(X,X)+np.eye(len(X))*.0025
 center=float(np.mean(y));scale=max(.02,float(np.std(y)));L=np.linalg.cholesky(K)
 alpha=np.linalg.solve(L.T,np.linalg.solve(L,(y-center)/scale));cross=kernel(X,T);mean=center+scale*(cross.T@alpha)
 var=np.maximum(1e-10,1.-np.sum(np.linalg.solve(L,cross)**2,axis=0));return mean,scale*np.sqrt(var)

def sequence(study,C):
 yield dict(tag='B',action={'family':'B'},category='optimization_anchor')
 yield dict(tag='BEST',action=C['strong_action'],category='optimization_anchor')
 baseline=evaluate(study.last_row['id']);dims=C['search_dimensions'];start=np.asarray(C['start_parameters'],float);budget=C['arm_budget'];summary={}
 for arm in ['PATTERN','BO']:
  rng=np.random.default_rng(C['search_seed']);X=[];Y=[];rows=[];center=start.copy();bestscore=float('inf');axis=0;mesh=.5;visited=[]
  for i in range(budget):
   pred=None
   if i==0:x=start.copy()
   elif arm=='PATTERN':
    for _ in range(32):
     dim=(axis//2)%len(dims);sign=1. if axis%2==0 else -1.;axis+=1;x=center.copy();x[dim]=np.clip(x[dim]+sign*mesh,-1,1)
     if axis%(2*len(dims))==0:mesh=max(.125,mesh*.5)
     if all(np.max(abs(x-u))>1e-10 for u in X):break
    else:x=np.clip(center+rng.uniform(-mesh,mesh,len(dims)),-1,1)
   elif i<=4:
    # Both methods have the same public initial action; each own trial is executed.
    x=np.clip(start+rng.uniform(-.7,.7,len(dims)),-1,1)
   else:
    pool=np.vstack([rng.uniform(-1,1,(1024,len(dims))),np.clip(center+rng.normal(0,.25,(1024,len(dims))),-1,1)])
    pool=np.array([z for z in pool if all(np.max(abs(z-u))>1e-5 for u in X)])
    mean,std=gp_predict(X,Y,pool);improve=min(Y)-mean-.002;z=improve/std;ei=improve*ndtr(z)+std*np.exp(-.5*z*z)/np.sqrt(2*np.pi);idx=int(np.argmax(ei));x=pool[idx]
    pred=dict(type='GP_BO_EI',predicted_score=float(mean[idx]),score_std=float(std[idx]),expected_improvement=float(ei[idx]),training_physical_attempts=len(X),proxy_queries=len(pool),only_own_arm_feedback=True,history='shared frozen start selection only; no feedback from the other optimizer')
   action=copy.deepcopy(C['strong_action'])
   for k,value in zip(dims,x):action['x'][k]=float(value)
   metadata=pred or dict(type='PATTERN' if arm=='PATTERN' else 'BO_INITIAL_DESIGN',only_own_arm_feedback=True,training_physical_attempts=len(X),proxy_queries=0)
   metadata.update(parameters=x.tolist(),objective='.65 combined raw jerk RMS ratio + .35 measured force-norm rate RMS ratio + .004*(JF-JF_strong) + .004*(JM-JM_strong); original qualification required',created_utc=utc())
   yield dict(tag=arm+f'{i+1:03d}',action=action,category='optimization',prediction=metadata)
   row=copy.deepcopy(study.last_row);score,extended=objective(row,baseline);X.append(x.copy());Y.append(score);rows.append(dict(id=row['id'],attempt_in_arm=i+1,parameters=x.tolist(),score=score,complete=row['complete'],qualified=row['qualified'],JF=row.get('JF'),JM=row.get('JM'),new_native_steps=row.get('actual_new_native_steps'),predicted=metadata))
   if score<bestscore:bestscore=score;center=x.copy()
   study.arm_rows[arm]=copy.deepcopy(rows);put('analysis/optimization/'+C['group']+'_'+arm+'.json',dict(arm=arm,budget=budget,completed=i+1,rows=rows,best_score=bestscore,only_own_feedback=True,common_initialization=C['start_parameters'],public_historical_selection=C.get('public_start_selection')))
  summary[arm]=rows
 put('analysis/optimization/'+C['group']+'_MATCHED_BUDGET.json',dict(arms=summary,fixed_checkpoints=[4,8,budget],extra_training_or_proxy_cost_separate=True,physical_budget_per_arm=budget,adaptive_extensions='NONE_IN_THIS_FIXED_COMPARISON'))
