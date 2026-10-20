"""Offline learning/evaluation figure; invoke only after final analysis."""
from pathlib import Path
import json,csv,shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_seed1_continuation')
L=W/'output_attempt3';S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1/source/stages/stage5_personalized_motion_learning');D=S/'docs/single_human_sac_seed1_continuation_v2_guardfix_attempt3'
def run():
    analysis=json.loads((L/'SAC_SEED1_FINAL_ANALYSIS.json').read_text());rows=[]
    for row in csv.DictReader((L/'SAC_SEED1_LEARNING_CURVE_COMBINED.csv').open()):
        try:rows.append((int(row['training_step']),float(row.get('reward_total') or row.get('episode_return')),str(row.get('success') or row.get('causal_task_complete')).lower()=='true'))
        except (TypeError,ValueError):pass
    previous=S/'docs/single_human_sac_seed1_continuation_v1_attempt2'
    rows.sort();evals=[json.loads(p.read_text()) for folder in (previous,D) for p in folder.glob('EVALUATION_*.json')];evals=[r for r in evals if r['tag']=='periodic'];evals.sort(key=lambda r:r['training_step'])
    fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained');a,b,c,d=axes.ravel()
    if rows:
        x=np.array([r[0] for r in rows])/1000;y=np.array([r[1] for r in rows]);success=np.array([r[2] for r in rows],float)
        a.scatter(x,y,s=5,alpha=.2,color='#54769c',label='Episode return')
        width=min(25,len(rows));a.plot(x[width-1:],np.convolve(y,np.ones(width)/width,'valid'),color='#17395c',label=f'{width}-episode mean')
        b.plot(x[width-1:],np.convolve(success,np.ones(width)/width,'valid')*100,color='#28634a',label='Causal training completion')
    colors={'NATIVE':'#276493','MATCHED':'#ad5722'}
    for scope,color in colors.items():
        rr=[r for r in evals if r['scope']==scope]
        for valid,marker in ((True,'o'),(False,'x')):
            ss=[r for r in rr if r['valid']==valid]
            if ss:c.scatter([r['training_step']/1000 for r in ss],[r['J_F'] for r in ss],marker=marker,color=color,label=f'{scope} '+('VALID' if valid else 'INVALID / not ranked'))
        if rr:d.plot([r['training_step']/1000 for r in rr],[r['force_peak'] for r in rr],'-o',markersize=3,color=color,label=f'{scope} force')
    moment=d.twinx()
    for scope,color in colors.items():
        rr=[r for r in evals if r['scope']==scope]
        if rr:moment.plot([r['training_step']/1000 for r in rr],[r['moment_peak'] for r in rr],'--s',markersize=3,color=color,label=f'{scope} moment')
    a.set(title='Training reward',ylabel='Return (unranked)');b.set(title='Causal training completion',ylabel='Rolling completion (%)',ylim=(-3,103));c.set(title='Deterministic evaluation',ylabel='J_F (N s)');d.set(title='Evaluation force and moment peaks',ylabel='Force peak (N)');moment.set_ylabel('Moment peak (Nm)')
    for ax in (a,b,c,d):
        ax.axvline(260.887,color='#666666',linestyle=':',linewidth=1,label='Guard fix / cold reset')
        ax.set_xlabel('Total training steps (thousands)');ax.grid(alpha=.2);handles,labels=ax.get_legend_handles_labels()
        if handles:ax.legend(fontsize=8,loc='best')
    handles,labels=moment.get_legend_handles_labels()
    if handles:moment.legend(handles,labels,fontsize=8,loc='lower right')
    fig.suptitle(f'Seed 1, unchanged R2 — {analysis["total_steps"]:,} total steps\nInvalid costs and causal training completion do not qualify a full-task policy',fontsize=13)
    out=L/'SAC_SEED1_LEARNING_FIGURE_V1.png';fig.savefig(out,dpi=160);plt.close(fig);shutil.copy2(out,D/out.name)
    shutil.copy2(Path(__file__),S/'scripts/single_human_sac_seed1_continuation_v2_guardfix_attempt3'/Path(__file__).name)
    print(out,flush=True)
if __name__=='__main__':run()
