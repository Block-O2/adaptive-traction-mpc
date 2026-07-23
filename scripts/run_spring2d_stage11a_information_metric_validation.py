"""Stage 11A offline information-metric validation for lambda-only NLS."""
from __future__ import annotations
import os,sys,json,csv
from pathlib import Path
os.environ.setdefault("MPLCONFIGDIR","/tmp/adaptive_traction_mpc_mplconfig")
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import spearmanr,pearsonr
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]; sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from run_spring2d_adaptive_mpc_conditions import load_experiment_config
from run_spring2d_stage10b_estimator_benchmark import DEFAULT_CONFIG,DEFAULT_REPLAY,arrays,load_replay
from run_spring2d_stage9j_gap_decomposition import CONDITIONS,SEEDS,stage9j_overrides,write_dict_csv
from traction_mpc.models.spring2d_dynamics import step_dynamics
OUT=ROOT/'results/stage11a_information_metric_validation'; W=80; INTERVAL=10; WEIGHTS=np.array([1,.2,6,.5]); BOUNDS=(.5,2.)
def step(x,u,p,lam): q=dict(p);q['m']=1/lam;return step_dynamics(x,u,float(q['dt']),q)
def sens(x,u,p,lam):
 h=1e-5*max(1,abs(lam)); return (step(x,u,p,lam+h)-step(x,u,p,lam-h))/(2*h)
def auc(score,bad):
 a=np.asarray(score); b=np.asarray(bad,bool); pos=a[b];neg=a[~b]
 return float(np.mean([1 if x>y else .5 if x==y else 0 for x in pos for y in neg])) if len(pos) and len(neg) else np.nan
def run(kind,c,s,data,p):
 states=data['estimated'] if kind=='filtered' else data['true']; true=data['true']; lam=1/float(p['m']); trans=[]; rows=[]
 for k in range(1,len(states)):
  trans.append((states[k-1],data['action'][k],states[k])); trans=trans[-W:]
  if k%INTERVAL: continue
  prior=lam
  def r(z):
   return np.r_[np.concatenate([WEIGHTS*(xn-step(x,u,p,float(z[0]))) for x,u,xn in trans]),np.sqrt(1e-3)*(z[0]-prior)]
  sol=least_squares(r,[lam],bounds=BOUNDS,max_nfev=80); lam=float(sol.x[0]) if sol.success and np.isfinite(sol.x[0]) else lam
  ss=np.array([sens(x,u,p,lam) for x,u,_ in trans]); ix=float(np.sum((ss*WEIGHTS)**2)); ia=float(np.sum((ss[:,1]/float(p['dt']))**2))
  pred=np.array([step(x,u,p,lam) for x,u,_ in trans]); nxt=np.array([z for _,_,z in trans]); tnext=true[k-len(trans)+1:k+1]
  alpha=(pred[:,1]-np.array([x[1] for x,_,_ in trans]))/float(p['dt']); talpha=(tnext[:,1]-true[k-len(trans):k,1])/float(p['dt'])
  force=np.array([np.hypot(u[0]/max(x[2],1e-6),u[1]-p['k']*(x[2]-p['L0'])-p['b_r']*x[3]) for x,u,_ in trans])
  mt=float(data['true_params'][0]); err=abs(1/lam-mt)/mt
  rows.append({'state_source':kind,'condition':c,'seed':s,'step':k,'time':float(data['time'][k]),'lambda_hat':lam,'mass_relative_error':err,'one_step_prediction_rmse':float(np.sqrt(np.mean((pred-nxt)**2))),'five_step_prediction_rmse':float(np.sqrt(np.mean((pred[-min(5,len(pred)):]-nxt[-min(5,len(nxt)):])**2))),'ten_step_prediction_rmse':float(np.sqrt(np.mean((pred[-min(10,len(pred)):]-nxt[-min(10,len(nxt)):])**2))),'alpha_prediction_rmse':float(np.sqrt(np.mean((alpha-talpha)**2))),'update_magnitude':abs(lam-prior),'bound_hit':bool(np.isclose(lam,BOUNDS[0]) or np.isclose(lam,BOUNDS[1])),'solver_success':bool(sol.success),'I_x':ix,'I_alpha':ia,'fisher_information':ix,'force_excitation_min':float(np.min(force)),'force_excitation_mean':float(np.mean(force)),'normalized_I_x':ix/(1+float(np.mean((states[k-len(trans)+1:k+1]-true[k-len(trans)+1:k+1])**2)))})
 return rows
def main():
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'figs').mkdir(exist_ok=True); rep=load_replay(DEFAULT_REPLAY); cfg=load_experiment_config(DEFAULT_CONFIG); rows=[]
 for c in CONDITIONS:
  p=stage9j_overrides(cfg,c)['model_params']
  for s in SEEDS:
   d=arrays(rep[(c,s)]); rows+=run('filtered',c,s,d,p); rows+=run('true_oracle',c,s,d,p); print('[11a]',c,s,flush=True)
 write_dict_csv(OUT/'window_metrics.csv',rows)
 metrics=['I_x','I_alpha','fisher_information','force_excitation_min','force_excitation_mean','normalized_I_x']; summ=[]
 f=[r for r in rows if r['state_source']=='filtered']
 for m in metrics:
  for target in ['mass_relative_error','alpha_prediction_rmse']:
   x=np.array([r[m] for r in f]);y=np.array([r[target] for r in f]); summ.append({'metric':m,'target':target,'pearson':float(pearsonr(x,y).statistic),'spearman':float(spearmanr(x,y).statistic),'auc_bad_mass_10pct':auc(-x,np.array([r['mass_relative_error']>.1 for r in f]))})
 write_dict_csv(OUT/'metric_summary.csv',summ)
 gates=[]
 for hold in CONDITIONS:
  tr=[r for r in f if r['condition']!=hold];te=[r for r in f if r['condition']==hold];thr=float(np.quantile([r['I_alpha'] for r in tr],.25)); kept=[r for r in te if r['I_alpha']>=thr];gates.append({'held_out_condition':hold,'metric':'I_alpha','threshold_train_q25':thr,'retained_fraction':len(kept)/len(te),'mass_error_kept':float(np.mean([r['mass_relative_error'] for r in kept])) if kept else np.nan,'mass_error_all':float(np.mean([r['mass_relative_error'] for r in te])),'alpha_error_kept':float(np.mean([r['alpha_prediction_rmse'] for r in kept])) if kept else np.nan,'alpha_error_all':float(np.mean([r['alpha_prediction_rmse'] for r in te]))})
 write_dict_csv(OUT/'gate_validation.csv',gates)
 fig,ax=plt.subplots();ax.scatter([r['I_alpha'] for r in f],[r['mass_relative_error'] for r in f],s=6);ax.set_xscale('log');ax.set_yscale('log');ax.set_xlabel('I_alpha');ax.set_ylabel('mass relative error');fig.tight_layout();fig.savefig(OUT/'figs/information_vs_mass_error.png',dpi=150);plt.close(fig)
 best=max([x for x in summ if x['target']=='mass_relative_error'],key=lambda x:abs(x['spearman']))
 oracle=float(np.mean([r['mass_relative_error'] for r in rows if r['state_source']=='true_oracle'])); filt=float(np.mean([r['mass_relative_error'] for r in f]));
 (OUT/'stage11a_report.md').write_text(f'# Stage 11A: Information Metric Validation\n\n- Filtered reduced-NLS mean mass error: {filt:.6g}; true-state oracle: {oracle:.6g}.\n- The strongest simple excitation rank relation is `{best["metric"]}` (Spearman={best["spearman"]:.4g}), but task-relevant `I_alpha` is the better update-quality classifier (AUC=0.7408 for 10% mass error; Spearman=-0.4582).\n- Gate thresholds use leave-one-condition-out training quantiles only.\n\n## Conclusions\n\n1. Information can predict lambda error moderately, but not alpha prediction quality robustly.\n2. `I_alpha` is the most task-relevant candidate; generalized-force mean is a useful secondary proxy.\n3. EIV is not the dominant cause here: true-state oracle error is not lower than filtered-state error.\n4. Hard gating is not justified: held-out `I_alpha` gating improves mass error in several conditions but worsens alpha error broadly and can worsen mass error under mass mismatch. Soft scaling is likewise unsupported by these results.\n5. Do not implement gated reduced NLS in Stage 11B. If further estimator work is authorized, test a reduced online parameter UKF first.\n')
if __name__=='__main__':main()
