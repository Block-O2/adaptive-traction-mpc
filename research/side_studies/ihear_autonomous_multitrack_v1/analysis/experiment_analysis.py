from pathlib import Path
import os,sys,json,time,hashlib,ast,copy,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
src=(R/'analysis/historical_audit.py').read_text();tree=ast.parse(src)
for name in ['load','terminal','variations']:
 exec(ast.get_source_segment(src,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)))
groups=[n[:-13] for n in []]
groups=[f.name[:-13] for f in P.glob('*_RESULTS.json') if f.name not in ['EXPERIMENT_RESULTS.json','VALIDATION_RESULTS.json'] and (P/(f.name[:-13]+'_PLAN.json')).exists()]
groups=sorted(groups,key=lambda g:read(P/(g+'_PLAN.json'))['frozen_unix'])
rows=[];Z={}
for group in groups:
 for rr in read(P/(group+'_RESULTS.json'))['rows']:
  r=copy.deepcopy(rr);ident=r['id'];z=load(P,ident);Z[ident]=z;m=z['metric'];r['complete_metrics']=m;r['terminal_response']=terminal(z);r['actual_variations']=variations(z)
  r['force_RMS_N']=float(np.sqrt(np.mean(z['f']**2)));r['events']=z['events']
  if r['candidate'].get('approach'):
   b=Z[group+'_B'];er=Z[group+'_ER'];ert=terminal(er)[1];newt=r['terminal_response'][1];r['ER_saving_retention_fraction']=(b['metric']['J_F_N_s']-m['J_F_N_s'])/(b['metric']['J_F_N_s']-er['metric']['J_F_N_s']);r['overshoot_change_vs_ER_deg']=newt['return_overshoot_below_goal_deg']-ert['return_overshoot_below_goal_deg'];r['delta_J_F_vs_ER_N_s']=m['J_F_N_s']-er['metric']['J_F_N_s'];r['delta_moment_vs_ER_Nm_s']=m['moment_integral_Nm_s']-er['metric']['moment_integral_Nm_s'];r['eligible_primary']=bool(r['all_original_qualifications'] and r['motion']['gain_percent']>=1. and r['ER_saving_retention_fraction']>=.8 and r['overshoot_change_vs_ER_deg']<0.)
   event=next(e for e in z['events'] if e['phase']=='RETURN' and e['slot']==3);cut=event['splice'];pre=z['t']<cut-1e-9;equal_grid=z['t'].shape==er['t'].shape and np.max(abs(z['t']-er['t']))<1e-8
   r['causal_response']=dict(first_intervention_splice_task_s=cut,grid_equal=bool(equal_grid),pre_splice_q_dq_exact=bool(equal_grid and np.array_equal(z['q'][pre],er['q'][pre]) and np.array_equal(z['v'][pre],er['v'][pre])))
   if equal_grid:
    diff=np.max(abs(np.c_[z['q']-er['q'],z['v']-er['v']]),axis=1);ix=np.flatnonzero(diff>1e-9)
    r['causal_response'].update(first_actual_difference_task_s=None if not len(ix) else float(z['t'][ix[0]]),max_actual_q_difference_deg=np.max(abs(z['q']-er['q']),axis=0).tolist(),max_actual_dq_difference_deg_s=np.max(abs(z['v']-er['v']),axis=0).tolist())
   ev=variations(er);r['variation_delta_vs_ER_percent']={ph:{key:100*(v/ev[ph][key]-1) for key,v in vals.items()} for ph,vals in r['actual_variations'].items()}
  elif r['candidate'].get('early'):
   parent=Z[group+'_D'];cut=next(e['splice'] for e in z['events'] if e['phase']=='RETURN' and e['slot']==1);pre=z['t']<cut-1e-9;equal_grid=z['t'].shape==parent['t'].shape and np.max(abs(z['t']-parent['t']))<1e-8
   r['causal_response']=dict(parent=group+'_D',first_intervention_splice_task_s=cut,grid_equal=bool(equal_grid),pre_splice_q_dq_exact=bool(equal_grid and np.array_equal(z['q'][pre],parent['q'][pre]) and np.array_equal(z['v'][pre],parent['v'][pre])))
   if equal_grid:
    diff=np.max(abs(np.c_[z['q']-parent['q'],z['v']-parent['v']]),axis=1);idx=np.flatnonzero(diff>1e-9)
    r['causal_response'].update(first_actual_difference_task_s=None if not len(idx) else float(z['t'][idx[0]]),max_actual_q_difference_deg=np.max(abs(z['q']-parent['q']),axis=0).tolist(),max_actual_dq_difference_deg_s=np.max(abs(z['v']-parent['v']),axis=0).tolist())
  rows.append(r)
put('EXPERIMENT_RESULTS.json',dict(status='COMPLETE' if all((P/(g+'_DONE.json')).exists() for g in groups) else 'INTERIM',evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',groups=groups,rows=rows,only_complete_task_ranking=True,no_cross_background_absolute_ranking=True))
for group in groups:
 tags=[r['id'] for r in rows if r['id'].startswith(group+'_')];colors=['#777777','#0072b2','#d55e00','#009e73','#cc79a7','#e69f00','#56b4e9'];fig,axs=plt.subplots(6,1,figsize=(13,15),sharex=True,layout='constrained')
 for tag,c in zip(tags,colors):
  z=Z[tag];t=z['t'];tf=z['tf'];axs[0].plot(t,z['q'][:,1],c=c,label=tag.split('_',1)[1]);axs[0].plot(tf,z['rq'][:,1],c=c,ls='--',alpha=.6);axs[1].plot(t,z['v'][:,1],c=c);axs[1].plot(tf,z['rv'][:,1],c=c,ls='--',alpha=.6);axs[2].plot(t,z['a'][:,1],c=c,lw=.8);axs[3].plot(tf,z['truth'][:,1]-z['rq'][:,1],c=c);axs[4].plot(tf,np.linalg.norm(z['allocator'],axis=1),c=c);axs[5].plot(tf,z['moment'],c=c)
 axs[0].set_ylim(8.,13.);axs[1].set_ylim(-10,7);axs[2].set_ylim(-50,90);axs[3].set_ylim(-1.4,.65)
 for ax,label in zip(axs,['Knee q (deg)','Knee dq (deg/s)','Knee raw a (deg/s2)','Actual minus ref (deg)','Allocator norm (Nm)','Cuff moment norm (Nm)']):ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(16.2,18.1)
 axs[0].axhline(9.5,c='black',ls=':',lw=.7);axs[0].legend(ncol=len(tags));axs[-1].set_xlabel('Task time (s); solid actual / dashed issued reference');fig.suptitle(group+' terminal response — zoomed q/dq/a views; full extrema are reported separately');fig.savefig(P/'figures'/(group+'_terminal_response.png'),dpi=150);plt.close(fig)
 fig,axs=plt.subplots(5,1,figsize=(13,14),sharex=True,layout='constrained')
 for tag,c in zip(tags,colors):
  z=Z[tag];t=z['t'];tf=z['tf'];axs[0].plot(t,z['v'][:,1],c=c,label=tag.split('_',1)[1]);axs[1].plot(t,z['a'][:,1],c=c,lw=.6);axs[2].plot(t,z['j'][:,1],c=c,lw=.6);axs[3].plot(tf,z['f'],c=c);axs[4].plot(tf,np.r_[0,np.cumsum(z['f'][:-1]*np.diff(tf))],c=c)
 for ax,label in zip(axs,['Knee velocity (deg/s)','Knee raw a (deg/s2)','Knee raw jerk (deg/s3)','Cuff force (N)','Cumulative J_F (N s)']):ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(0,19.03)
 axs[0].legend(ncol=len(tags));axs[-1].set_xlabel('Complete task time (s)');fig.suptitle(group+' full motion and force — no partial-cost ranking');fig.savefig(P/'figures'/(group+'_full_motion_force.png'),dpi=150);plt.close(fig)
if all(g in groups for g in ['Adev','Bmap']) and all(g+'_'+arm in Z for g in ['Adev','Bmap'] for arm in ['B','T','D','ER']):
 fig,axs=plt.subplots(2,3,figsize=(15,9),layout='constrained');arms=['B','T','D','ER'];x=np.arange(4)
 for group,shift,c,label in [('Adev',-.18,'#0072b2','W1'),('Bmap',.18,'#d55e00','R0 exposed')]:
  rr={a:next(r for r in rows if r['id']==group+'_'+a) for a in arms};bb=rr['B']['complete_metrics']['motion']['raw']['full']
  values=[[rr[a]['complete_metrics']['motion']['raw']['full']['velocity_deg_s']['p95_abs'][1] for a in arms],[rr[a]['motion']['burden_ratios']['velocity_deg_s/p95_abs'][1] for a in arms],[rr[a]['terminal_response'][1]['return_overshoot_below_goal_deg'] for a in arms],[rr[a]['complete_metrics']['motion']['raw']['full']['acceleration_deg_s2']['p95_abs'][1] for a in arms],[rr[a]['motion']['burden_ratios']['acceleration_deg_s2/p95_abs'][1] for a in arms],[rr[a]['motion']['excursion_delta_deg'][1] for a in arms]]
  for ax,y in zip(axs.flat,values):ax.bar(x+shift,y,width=.34,color=c,label=label);ax.set_xticks(x,arms);ax.grid(axis='y',alpha=.2)
 for ax,title in zip(axs.flat,['Absolute knee v95 (deg/s)','Knee v95 / own matched B','True knee undershoot (deg)','Absolute knee a95 (deg/s2)','Knee a95 / own matched B','Knee excursion minus own B (deg)']):ax.set_title(title)
 axs[0,1].axhline(1.1,c='red',ls=':');axs[1,1].axhline(1.1,c='red',ls=':');axs[1,2].axhline(.5,c='red',ls=':');axs[0,0].legend();fig.suptitle('New paired state diagnostic: absolute burden and relative qualification must be separated');fig.savefig(P/'figures/W1_R0_state_diagnostic.png',dpi=150);plt.close(fig)
for f in [P/'EXPERIMENT_RESULTS.json',*list((P/'figures').glob('*terminal_response.png')),*list((P/'figures').glob('*full_motion_force.png')),*list((P/'figures').glob('*state_diagnostic.png'))]:
 dst=R/f.relative_to(P);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
print(json.dumps(dict(status='PASS',groups=groups,rows=[dict(id=r['id'],JF=r['J_F_N_s'],qualified=r['all_original_qualifications'],eligible=r.get('eligible_primary'),failed=r['motion']['failed_requirements'],knee_overshoot=r['terminal_response'][1]['return_overshoot_below_goal_deg'],excursion_delta=r['motion']['excursion_delta_deg'],variation=r.get('variation_delta_vs_ER_percent',{}).get('full')) for r in rows])),flush=True)
