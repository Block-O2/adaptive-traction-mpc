"""Standalone scientific plots from saved evidence; no physics or policy updates."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.colors import ListedColormap
P=Path(__file__).resolve().parent
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140,'savefig.dpi':180})
def read(n):return json.loads((P/n).read_text())
def save(fig,n):fig.savefig(P/'figures'/n,bbox_inches='tight');plt.close(fig)
def main():
    result=read('LEARNING_RESULTS.json');rows=result['rows'];cont=read('CONTINUOUS_REPETITION_RESULTS.json')
    fig,ax=plt.subplots(figsize=(11,3));ax.axis('off')
    labels=['Trial 1: fixed B\nreal coupled physics','Causal history\nphase / progress\n5 ms samples','Frozen update\nILC / GP / value','Trial 2 live fork\nfixed / enabled /\ndisabled','Safety > task\noriginal motion gates\ncompare full J_F']
    for i,label in enumerate(labels):
        x=.01+i*.2;ax.add_patch(FancyBboxPatch((x,.35),.17,.4,boxstyle='round,pad=.008',transform=ax.transAxes,fc='#eef4fa',ec='#336a9f'))
        ax.text(x+.085,.55,label,transform=ax.transAxes,va='center',ha='center',fontsize=9)
        if i<4:ax.annotate('',xy=(x+.19,.55),xytext=(x+.179,.55),xycoords='axes fraction',arrowprops=dict(arrowstyle='->',color='#336a9f'))
    ax.text(.01,.12,'Patient native truth: offline labels / diagnostics only. No qpos/qvel resets between repetitions.',transform=ax.transAxes,fontsize=10)
    save(fig,'01_history_to_action.png')
    methods=['B','ILC','ILC_DISABLED','BO','BO_DISABLED','VALUE','VALUE_DISABLED','H150'];patients=list(dict.fromkeys(r['patient_id'] for r in rows))
    fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True)
    colors=dict(zip(methods[1:],plt.cm.tab10.colors));colors['B']='#777777'
    for k,method in enumerate(methods):
        rr=[r for r in rows if r['method']==method]
        x=[patients.index(r['patient_id'])+(k-3.5)*.08 for r in rr]
        for ax,key,title in [(axes[0],'gain_vs_B_N_s','Force gain vs matched fixed B (N s)'),(axes[1],'moment_Nm_s','Full cuff moment integral (N m s)')]:
            good=[(xx,r) for xx,r in zip(x,rr) if r[key] is not None]
            ax.scatter([v[0] for v in good],[v[1][key] for v in good],label=method,color=colors[method],s=30)
            bad=[v for v in good if not v[1]['complete_qualified']]
            if bad:ax.scatter([v[0] for v in bad],[v[1][key] for v in bad],marker='x',s=90,color='red')
            ax.set_ylabel(title);ax.grid(alpha=.2)
        good=[(xx,r) for xx,r in zip(x,rr) if r['tracking_RMS_deg'] is not None]
        axes[2].scatter([v[0] for v in good],[v[1]['tracking_RMS_deg'][1] for v in good],color=colors[method],label=method,s=30)
    axes[0].axhline(0,c='black',lw=.8);axes[0].set_yscale('symlog',linthresh=.1);axes[0].set_ylim(-1.3,70);axes[0].set_ylabel('Force gain vs B (N s; symlog)');axes[2].set_ylabel('Knee tracking RMS (deg; 5 ms truth)');axes[2].set_xticks(range(len(patients)),patients);axes[2].grid(alpha=.2)
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,ncol=4,fontsize=8,loc='upper center',bbox_to_anchor=(.5,.965))
    fig.suptitle('Complete task outcomes; red x = original qualification failure');fig.tight_layout(rect=(0,0,1,.91));save(fig,'02_methods_force_moment_tracking.png')
    if cont['third_repetition']:
        fig,axes=plt.subplots(1,2,figsize=(10,4))
        for tr in cont['third_repetition']:
            pid=tr['patient_id'];group=next(g for g in cont['first_second_groups'] if g['patient_id']==pid)
            t2=next(r for r in rows if r['patient_id']==pid and r['method']=='ILC');by={r['method']:r for r in tr['rows']}
            axes[0].plot([1,2,3],[0.,t2['JF_N_s']-group['first_JF_N_s'],by['ILC']['J_F_N_s']-group['first_JF_N_s']],'-o',label=pid)
            axes[1].plot([2,3],[t2['gain_vs_B_N_s'],tr['improvement_vs_KEEP_N_s']],'-o',label=pid)
        axes[0].set(title='Continuous branch: change from Trial 1',xlabel='Trial',ylabel='Complete J_F minus Trial 1 (N s)',xticks=[1,2,3]);axes[0].legend();axes[1].set(title='Matched contribution',xticks=[2,3],xticklabels=['T2 vs B','T3 update vs KEEP'],ylabel='Force gain (N s)');axes[1].axhline(0,c='black',lw=.8)
        for ax in axes:ax.grid(alpha=.2)
        fig.text(.02,-.03,'Left: descriptive across different initial states. Right: matched forks establish the update comparison.',fontsize=9)
        save(fig,'03_continuous_trials.png')
    selected=next((r for r in rows if r['method']=='ILC' and r['patient_id']=='P00'),None)
    if selected:
        group='P00R';fig,axes=plt.subplots(4,1,figsize=(11,10),sharex=True);saved_forces=[]
        for ident,label,color in [(group+'_T2_B','Fixed B','#555555'),(selected['id'],'History ILC','#147d92')]:
            with np.load(P/'source/results'/ident/'trace.npz') as z:
                m=z['stage']=='TASK';t=z['time_s'][m]-z['time_s'][m][0];q=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][m,:2]);ref=np.rad2deg(z['reference_q_rad'][m]);force=np.linalg.norm(z['physical_cuff_force_world_n'][m],axis=1)
                axes[0].plot(t,q[:,0],c=color,label=label+' actual');axes[1].plot(t,q[:,1],c=color,label=label+' actual');axes[2].plot(t,force,c=color,label=label)
                saved_forces.append(force)
                if label=='Fixed B':
                    axes[0].plot(t,ref[:,0],'--',c='#bd5959',lw=1,label='B reference');axes[1].plot(t,ref[:,1],'--',c='#bd5959',lw=1,label='B reference')
                else:axes[1].plot(t,ref[:,1],':',c='#2654a4',lw=1,label='ILC reference')
        axes[3].plot(t,saved_forces[1]-saved_forces[0],color='#147d92');axes[3].axhline(0,c='black',lw=.6);axes[3].set_ylabel('ILC force minus B (N)');axes[3].grid(alpha=.2)
        for ax,title in zip(axes,['Hip (deg)','Knee (deg)','Cuff force (N)']):ax.set_ylabel(title);ax.legend(fontsize=8);ax.grid(alpha=.2)
        axes[-1].set_xlabel('Task time (s), aligned only within this matched patient');save(fig,'04_actual_motion_force.png')
    pred=result['predictions']
    if pred:
        fig,aa=plt.subplots(1,2,figsize=(11,5));ax=aa[0]
        for method in sorted({r['method'] for r in pred}):
            rr=[r for r in pred if r['method']==method and r['actual_JF_N_s'] is not None]
            marker={'BO':'o','BO_DISABLED':'x','VALUE':'s','VALUE_DISABLED':'+'}[method]
            ax.scatter([r['predicted_JF_N_s'] for r in rr],[r['actual_JF_N_s'] for r in rr],label=method,marker=marker,color=colors[method],s=45,alpha=.8)
            aa[1].scatter([r['predicted_gain_vs_B_N_s'] for r in rr],[r['actual_gain_vs_B_N_s'] for r in rr],label=method,marker=marker,color=colors[method],s=45,alpha=.8)
            for r in rr:
                if abs(r['actual_gain_vs_B_N_s'])>.01:aa[1].annotate(r['patient_id'],(r['predicted_gain_vs_B_N_s'],r['actual_gain_vs_B_N_s']),xytext=(4,8 if r['actual_gain_vs_B_N_s']<0 else -15),textcoords='offset points',fontsize=8)
        values=[v for r in pred for v in [r['actual_JF_N_s'],r['predicted_JF_N_s']] if v is not None];lo=min(values);hi=max(values);ax.plot([lo,hi],[lo,hi],'--',color='grey')
        ax.set(xlabel='Predicted full J_F (N s)',ylabel='Observed full J_F (N s)',title='Full cost; disabled uses population offset');ax.legend(fontsize=8);ax.grid(alpha=.2)
        aa[1].set(xlabel='Predicted gain vs B (N s)',ylabel='Observed gain vs B (N s)',title='Within-context action advantage');aa[1].axhline(0,c='grey',lw=.7);aa[1].axvline(0,c='grey',lw=.7);aa[1].grid(alpha=.2);fig.tight_layout();save(fig,'05_prediction_vs_observation.png')
    fig,ax=plt.subplots(figsize=(11,5.5));matrix=np.full((len(methods),len(patients)),np.nan)
    for i,m in enumerate(methods):
        for j,pid in enumerate(patients):
            r=next((r for r in rows if r['method']==m and r['patient_id']==pid),None)
            if r:matrix[i,j]=1 if r['complete_qualified'] else 0
    attempts=read('ATTEMPT_ACCOUNTING.json')['attempts'];ticklabels=[]
    for pid in patients:
        rr=[r for r in attempts if r['patient_id']==pid]
        ticklabels.append(pid+'\n'+str(len(rr))+' START / '+str(sum(r['complete_task'] for r in rr))+' full\n'+format(sum(r['actual_new_native_steps'] for r in rr)/1e6,'.2f')+'M steps')
    ax.imshow(matrix,vmin=0,vmax=1,cmap=ListedColormap(['#f1b9bf','#bce4cf']),aspect='auto');ax.set_xticks(range(len(patients)),ticklabels,fontsize=8);ax.set_yticks(range(len(methods)),methods)
    for i in range(len(methods)):
        for j in range(len(patients)):ax.text(j,i,'NOT RUN' if np.isnan(matrix[i,j]) else 'PASS' if matrix[i,j] else 'FAIL',ha='center',va='center',fontsize=8)
    ax.set_title('Original full qualification: safety, task, execution and relative motion');ax.set_xlabel('Costs include all trials, preparation and failed attempts; native steps are not independent samples.',fontsize=9);save(fig,'06_qualification_matrix.png')
    print('FIGURES',len(list((P/'figures').glob('*.png'))),flush=True)
if __name__=='__main__':main()
