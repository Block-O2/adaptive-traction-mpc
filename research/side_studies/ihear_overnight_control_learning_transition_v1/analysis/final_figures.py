"""Publication-style static figures from completed raw evidence only."""
from pathlib import Path
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;A=P.parent/'ihear_model_terminal_compensation_v1'
fig,axs=plt.subplots(2,2,figsize=(12,8),sharex=True,layout='constrained')
for col,g in enumerate(['D01R','D03']):
    cases=[(P,g+'_'+a,a) for a in ['B','H150','ZERO']]
    if g=='D01R':cases.append((A,'Ctrl_ER','Historical ER'))
    for root,ident,label in cases:
        z=np.load(root/'source/results'/ident/'trace.npz');mask=z['stage']=='TASK';t=z['time_s'][mask];t=t-t[0]
        axs[0,col].plot(t,np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][mask,1]),label=label)
        axs[1,col].plot(t,np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1),label=label)
    axs[0,col].axhline(9.5,ls=':',c='black',lw=1,label='Issued final knee target')
    axs[0,col].set_ylim(8,11.8);axs[0,col].set_title(g+' terminal response');axs[0,col].legend(fontsize=8)
    axs[1,col].set_xlabel('Task time (s)')
    for row in range(2):axs[row,col].set_xlim(16,19.1);axs[row,col].grid(alpha=.25)
axs[0,0].set_ylabel('Actual knee angle (deg)');axs[1,0].set_ylabel('Cuff force norm (N)')
fig.savefig(P/'figures/07_terminal_response.png',dpi=170);plt.close(fig)
ex=json.loads((P/'EXPERIMENT_RESULTS.json').read_text());lr=json.loads((P/'LEARNING_RESULTS_FINAL.json').read_text());groups=[r['parent'] for r in lr['rows']]
# Improve the export legend using preserved evaluation data only; do not refit
# or rewrite LEARNING_RESULTS.json.
fig,axs=plt.subplots(1,2,figsize=(13,5),layout='constrained')
actions=['H150','HIP','KNEE','ZERO']
for a in range(1,4):
    values=[r['actual_delta_J_F_N_s'][a] for r in lr['rows']]
    axs[0].plot(groups,values,marker='o',label=actions[a]+' minus H150')
    for i,r in enumerate(lr['rows']):
        if not r['qualified'][actions[a]]:axs[0].scatter(i,values[i],color='red',marker='x',s=65,zorder=4)
axs[0].scatter([],[],color='red',marker='x',s=65,label='Failed original qualification')
axs[0].axhline(0,c='black',lw=.7);axs[0].set_ylabel('Full-task force cost difference (N s)');axs[0].tick_params(axis='x',rotation=45);axs[0].legend(fontsize=8)
axs[0].set_title('Cost labels; qualification assessed separately')
for split,color in [('train','#7f7f7f'),('validation','#e69f00'),('test','#0072b2')]:
    selected=[r for r in lr['rows'] if r['split']==split]
    axs[1].scatter(np.array([r['actual_delta_J_F_N_s'] for r in selected]).ravel(),np.array([r['predicted_delta_J_F_N_s'] for r in selected]).ravel(),label=split,c=color,alpha=.8)
maximum=max(max(r['actual_delta_J_F_N_s']) for r in lr['rows'])*1.1
axs[1].plot([-.05,maximum],[-.05,maximum],ls=':',c='black');axs[1].set_xlabel('Actual full-task difference from H150 (N s)');axs[1].set_ylabel('Frozen Q predicted difference (N s)');axs[1].legend();axs[1].set_title('Accurate cost prediction does not imply policy gain')
for ax in axs:ax.grid(alpha=.25)
fig.savefig(P/'figures/04_Q_prediction_actual.png',dpi=170);plt.close(fig)
fig,axs=plt.subplots(2,1,figsize=(12,8),sharex=True,layout='constrained')
for action in ['H150','HIP','KNEE','ZERO']:
    rs=[next(r for r in ex['rows'] if r['parent']==g and r['action']==action) for g in groups]
    axs[0].plot(groups,[r['excursion_gate_margin_deg'] for r in rs],marker='o',label=action)
    axs[1].plot(groups,[r['J_F_N_s']-next(v['J_F_N_s'] for v in ex['rows'] if v['parent']==r['parent'] and v['action']=='H150') for r in rs],marker='o',label=action)
    for i,r in enumerate(rs):
        if not r['qualified']:axs[0].scatter(i,r['excursion_gate_margin_deg'],marker='x',s=80,c='red')
axs[0].axhline(0,c='black',lw=1);axs[0].set_ylabel('Original excursion gate margin (deg)');axs[0].legend(ncol=4);axs[1].set_ylabel('Full J_F difference from H150 (N s)')
for ax in axs:ax.grid(alpha=.25);ax.axvline(5.5,c='grey',ls=':');ax.axvline(7.5,c='grey',ls=':')
axs[0].set_title('Qualification margin and cost are separate outcomes; red x = unqualified')
axs[1].set_xlabel('Registered parent state (train / validation / test)');fig.savefig(P/'figures/08_qualification_cost.png',dpi=170);plt.close(fig)
ds=json.loads((P/'derived/DATASET_all.json').read_text());features=[];margin=[]
for group in groups:
    r=next(r for r in ds['records'] if r['parent']==group and r['proposed_action']['id']=='H150')
    if r['split']!='train':continue
    features.append(r['state']['features']);margin.append(next(v['excursion_gate_margin_deg'] for v in ex['rows'] if v['parent']==group and v['action']=='H150'))
x=np.array(features);y=np.array(margin);corr=[]
for i,name in enumerate(ds['feature_names']):
    c=None if x[:,i].std()<1e-10 else float(np.corrcoef(x[:,i],y)[0,1])
    corr.append(dict(feature=name,train_min=float(x[:,i].min()),train_max=float(x[:,i].max()),pearson_with_excursion_margin=c))
(P/'derived/STATE_MARGIN_ASSOCIATIONS.json').write_text(json.dumps(dict(scope='exploratory development-only association, not causal attribution or post-test policy change',independent_parents=len(x),single_Human=True,features=corr),indent=2)+'\n')
extrema=[]
for group in groups:
    arms={}
    for action in ['B','H150','ZERO']:
        z=np.load(P/'motion_series'/(group+'_'+action+'.npz'));q=np.rad2deg(z['true_q_rad'])
        arms[action]=dict(min_deg=q.min(0).tolist(),max_deg=q.max(0).tolist(),excursion_deg=np.ptp(q,axis=0).tolist())
    extrema.append(dict(parent=group,arms=arms,interpretation='Matched-B excursion qualification depends on both candidate and B extrema; similar absolute candidate undershoot can receive different qualification under different legal prefixes.'))
(P/'derived/EXCURSION_EXTREMA_DIAGNOSTIC.json').write_text(json.dumps(dict(rows=extrema,original_relative_gate_unchanged=True),indent=2)+'\n')
print('FINAL_FIGURES_COMPLETE',flush=True)
