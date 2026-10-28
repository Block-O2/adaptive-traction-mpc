"""Standalone scientific charts; complete dose and failed partial kept separate."""
from pathlib import Path
import sys,json
from collections import defaultdict
from research_common import ROOT,atomic,now,sha
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    rows=[json.loads(x) for x in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    train=[x for x in rows if x['mode']=='training'];ev=[x for x in rows if x['mode']=='evaluation']
    branches=sorted({x['branch'] for x in train});colors={b:plt.cm.tab10(i%10) for i,b in enumerate(branches)}
    fig,axes=plt.subplots(4,2,figsize=(14,13),sharex='col',constrained_layout=True)
    for col,seed in enumerate([1495656323,1630784693]):
        for b in branches:
            rr=sorted((x for x in train if x['seed']==seed and x['branch']==b),key=lambda x:x['index'])
            if not rr:continue
            index=np.asarray([x['index'] for x in rr]);success=np.asarray([x['success'] for x in rr],float)
            smooth=np.asarray([success[max(0,i-9):i+1].mean() for i in range(len(success))])
            axes[0,col].plot(index,smooth,color=colors[b],label=b)
            axes[1,col].plot(index,[x['task_s'] for x in rr],'.-',color=colors[b],alpha=.7)
            updated=[x for x in rr if x['update']]
            axes[2,col].plot([x['index'] for x in updated],[x['update']['losses'].get('train/value_loss',np.nan) for x in updated],'.-',color=colors[b],alpha=.7)
            axes[3,col].plot([x['index'] for x in updated],[x['update']['losses'].get('train/approx_kl',np.nan) for x in updated],'.-',color=colors[b],alpha=.7)
        axes[0,col].set_title(f'Continuation from original050, training seed {seed}')
        for row,label in enumerate(['Training COMPLETE, trailing <=10 episodes','Executed task duration (s)','Value loss (reward scales differ)','Recorded approximate KL']):
            axes[row,col].set_ylabel(label);axes[row,col].grid(alpha=.25)
        axes[3,col].set_xlabel('New continuation training episode')
        axes[0,col].set_ylim(-.05,1.05)
    axes[0,0].legend(fontsize=7,loc='best')
    fig.suptitle('Exploratory development learning curves; training success is not frozen-policy qualification')
    outputs=[]
    for ext in ['png','pdf']:
        p=ROOT/'TRAINING_CURVES'/f'PPO_learning_curves.{ext}';fig.savefig(p,dpi=180);outputs.append(p)
    plt.close(fig)
    if ev:
        fig,axes=plt.subplots(4,2,figsize=(14,13),sharex=True,sharey='row',constrained_layout=True)
        historical=[json.loads(x) for x in (ROOT.parent/'rl_b_autonomous_replication_v1/ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
        ticks=sorted({0,*[x['index']-1 for x in ev]})
        for col,seed in enumerate([1495656323,1630784693]):
            ee=[x for x in ev if x['seed']==seed]
            for b in sorted({x['branch'] for x in ee}):
                for mode,marker in [('deterministic','o'),('stochastic','x')]:
                    rr=[x for x in ee if x['branch']==b and x['policy_mode']==mode]
                    if not rr:continue
                    label=f'{b}/{mode}';c=colors.get(b,'gray')
                    axes[0,col].scatter([x['index']-1 for x in rr],[float(x['success']) for x in rr],marker=marker,c=[c],label=label,alpha=.75)
                    axes[1,col].scatter([x['index']-1 for x in rr],[x['task_s'] for x in rr],marker=marker,c=[c],alpha=.75)
                    complete=[x for x in rr if x['success']]
                    axes[2,col].scatter([x['index']-1 for x in complete],[x['JF'] for x in complete],marker=marker,c=[c],alpha=.75)
                    axes[3,col].scatter([x['index']-1 for x in complete],[x['JM'] for x in complete],marker=marker,c=[c],alpha=.75)
            parent=next(x for x in historical if x['training_seed']==seed and x['kind']=='checkpoint050_first')
            for i,value in enumerate([1.,parent['task_s'],parent['JF'],parent['JM']]):
                axes[i,col].scatter([0],[value],marker='s',c='black',s=28,
                    label='Original050 mean (historical)' if i==0 else None)
            axes[0,col].set_title(f'Frozen nominal evaluation, seed {seed}')
            axes[0,col].set_ylim(-.1,1.1);axes[0,col].set_ylabel('Original runtime COMPLETE')
            axes[1,col].set_ylabel('Executed task duration (s)')
            axes[2,col].set_ylabel('COMPLETE task JF (N s)')
            axes[3,col].set_ylabel('COMPLETE task JM (Nm s)');axes[3,col].set_xlabel('Continuation checkpoint episode')
            axes[3,col].set_xticks(ticks)
            for ax in axes[:,col]:ax.grid(alpha=.25)
        handles,labels=axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,fontsize=7,loc='lower center',bbox_to_anchor=(.5,-.035),ncol=3)
        fig.suptitle('Frozen nominal task outcomes and executed duration; complete-task dose only\nCheck task duration before comparing JF/JM; no independent initial-state or B/H150 matched claim')
        for ext in ['png','pdf']:
            p=ROOT/'TRAINING_CURVES'/f'Frozen_task_and_dose.{ext}';fig.savefig(p,dpi=180,bbox_inches='tight');outputs.append(p)
        plt.close(fig)
    atomic(ROOT/'TRAINING_CURVES/MANIFEST.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),
        files=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in outputs],
        note='Descriptive development figures. Different reward-scale value losses are not quality rankings. No independent initial-state claim.'))
    print('plotted',len(outputs),'artifacts')
if __name__=='__main__':main()
