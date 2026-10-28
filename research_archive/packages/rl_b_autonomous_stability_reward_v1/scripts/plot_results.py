"""Standalone scientific charts; complete dose and failed partial kept separate."""
from pathlib import Path
import sys,json
from collections import defaultdict
from research_common import ROOT,atomic,now,sha,read
from stability_lineages import resolve
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    rows=[json.loads(x) for x in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    train=[x for x in rows if x['mode']=='training'];ev=[x for x in rows if x['mode']=='evaluation']
    lineage_map=read(ROOT/'STABILITY_LINEAGES.json',{}).get('branch_to_lineage',{})
    ancestry=resolve(rows,lineage_map);assert ancestry['status']=='PASS',ancestry['errors']
    for row in rows:row['plot_lineage']=lineage_map.get(row['branch'],row['branch'])
    for row in ev:
        directory=Path(row['run']).parent
        cfg=read(directory/'EFFECTIVE_CONFIG.json') or read(directory/'START.json',{}).get('config',{})
        row['evaluation_split']=cfg.get('evaluation_split','development')
        row['evaluation_rng']=cfg.get('evaluation_rng')
    branches=sorted({x['plot_lineage'] for x in train});colors={b:plt.cm.tab10(i%10) for i,b in enumerate(branches)}
    fig,axes=plt.subplots(4,2,figsize=(14,13),sharex='col',constrained_layout=True)
    for col,seed in enumerate([1495656323,1630784693]):
        for b in branches:
            rr=sorted((x for x in train if x['seed']==seed and x['plot_lineage']==b),key=lambda x:x['index'])
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
        positions={episode:i for i,episode in enumerate(ticks)}
        families=sorted({x['plot_lineage'] for x in ev})
        offsets=dict(zip(families,np.linspace(-.35,.35,len(families))))
        def locations(records,branch,mode,held=False):
            shift=offsets[branch]+(-.035 if mode=='deterministic' else .035)+(.075 if held else 0.)
            return [positions[x['index']-1]+shift for x in records]
        for col,seed in enumerate([1495656323,1630784693]):
            ee=[x for x in ev if x['seed']==seed]
            for b in sorted({x['plot_lineage'] for x in ee}):
                for mode,marker in [('deterministic','o'),('stochastic','x')]:
                    rr_all=[x for x in ee if x['plot_lineage']==b and x['policy_mode']==mode]
                    rr=[x for x in rr_all if x['evaluation_split']=='development']
                    if not rr and not rr_all:continue
                    label=f'{b}/{mode}/dev';c=colors.get(b,'gray')
                    axes[0,col].scatter(locations(rr,b,mode),[float(x['success']) for x in rr],marker=marker,c=[c],label=label,alpha=.75)
                    axes[1,col].scatter(locations(rr,b,mode),[x['task_s'] for x in rr],marker=marker,c=[c],alpha=.75)
                    complete=[x for x in rr if x['success']]
                    axes[2,col].scatter(locations(complete,b,mode),[x['JF'] for x in complete],marker=marker,c=[c],alpha=.75)
                    axes[3,col].scatter(locations(complete,b,mode),[x['JM'] for x in complete],marker=marker,c=[c],alpha=.75)
                    held=[x for x in rr_all if x['evaluation_split']!='development']
                    if held:
                        axes[0,col].scatter(locations(held,b,mode,True),[float(x['success']) for x in held],marker='D',c=[c],label=f'{b}/{mode}/heldout actions',alpha=.7)
                        axes[1,col].scatter(locations(held,b,mode,True),[x['task_s'] for x in held],marker='D',c=[c],alpha=.7)
                        good=[x for x in held if x['success']]
                        axes[2,col].scatter(locations(good,b,mode,True),[x['JF'] for x in good],marker='D',c=[c],alpha=.7)
                        axes[3,col].scatter(locations(good,b,mode,True),[x['JM'] for x in good],marker='D',c=[c],alpha=.7)
            parent=next(x for x in historical if x['training_seed']==seed and x['kind']=='checkpoint050_first')
            for i,value in enumerate([1.,parent['task_s'],parent['JF'],parent['JM']]):
                axes[i,col].scatter([0],[value],marker='s',c='black',s=28,
                    label='Original050 mean (historical)' if i==0 else None)
            axes[0,col].set_title(f'Frozen nominal evaluation, seed {seed}')
            axes[0,col].set_ylim(-.1,1.1);axes[0,col].set_ylabel('Original runtime COMPLETE')
            axes[1,col].set_ylabel('Executed task duration (s)')
            axes[2,col].set_ylabel('COMPLETE task JF (N s)')
            axes[3,col].set_ylabel('COMPLETE task JM (Nm s)');axes[3,col].set_xlabel('Continuation checkpoint episode (categorical groups)')
            axes[3,col].set_xticks(list(positions.values()),ticks)
            for ax in axes[:,col]:ax.grid(alpha=.25)
        handles,labels=axes[0,0].get_legend_handles_labels()
        fig.legend(handles,labels,fontsize=7,loc='lower center',bbox_to_anchor=(.5,-.035),ncol=3)
        fig.suptitle('Frozen nominal task outcomes and executed duration; complete-task dose only\nOffsets separate records at the same checkpoint; check task duration before comparing JF/JM\nNo independent initial-state or B/H150 matched claim')
        for ext in ['png','pdf']:
            p=ROOT/'TRAINING_CURVES'/f'Frozen_task_and_dose.{ext}';fig.savefig(p,dpi=180,bbox_inches='tight');outputs.append(p)
        plt.close(fig)
    held=[x for x in ev if x['evaluation_split']!='development']
    if len(held)==8 and all(sum(x['seed']==seed for x in held)==4 for seed in [1495656323,1630784693]):
        assert len({x['plot_lineage'] for x in held})==1,'MIXED_HELDOUT_FAMILIES'
        rngs=sorted({x['evaluation_rng'] for x in held});assert len(rngs)==4
        fig,axes=plt.subplots(4,2,figsize=(13,11),sharex=True,sharey='row',constrained_layout=True)
        for col,seed in enumerate([1495656323,1630784693]):
            items=sorted((x for x in held if x['seed']==seed),key=lambda x:x['evaluation_rng'])
            assert [x['evaluation_rng'] for x in items]==rngs
            xx=np.arange(4);colors_held=['#387f72' if x['success'] else '#b85d45' for x in items]
            axes[0,col].bar(xx,[int(x['success']) for x in items],color=colors_held)
            axes[1,col].bar(xx,[x['task_s'] for x in items],color=colors_held)
            axes[2,col].scatter([i for i,x in enumerate(items) if x['success']],[x['JF'] for x in items if x['success']],color='#387f72')
            axes[3,col].scatter([i for i,x in enumerate(items) if x['success']],[x['JM'] for x in items if x['success']],color='#387f72')
            for i,item in enumerate(items):
                if not item['success']:
                    axes[0,col].scatter([i],[0],marker='x',color='#b85d45',s=65,zorder=4)
                    axes[0,col].annotate('ABORTED',(i,.02),xytext=(0,5),textcoords='offset points',ha='center',color='#b85d45',fontsize=9)
                    axes[1,col].annotate(f"{item['task_s']:.3f} s",(i,item['task_s']),xytext=(0,5),textcoords='offset points',ha='center',color='#b85d45',fontsize=9)
            axes[0,col].set_title(f'Seed {seed}; fixed checkpoint {items[0]["index"]-1}')
            axes[0,col].set_ylim(-.05,1.1)
            for row,label in enumerate(['Original runtime COMPLETE','Executed TASK duration (s)','COMPLETE task JF (N s)','COMPLETE task JM (Nm s)']):
                axes[row,col].set_ylabel(label);axes[row,col].grid(axis='y',alpha=.25)
            axes[3,col].set_xticks(xx,[str(v) for v in rngs],rotation=25,ha='right')
            axes[3,col].set_xlabel('Previously unseen action RNG; same nominal physics')
        fig.suptitle('One frozen checkpoint per selected parent; eight final action streams\nFailed partial dose excluded; four streams are descriptive, not independent physical initial states')
        for ext in ['png','pdf']:
            p=ROOT/'TRAINING_CURVES'/f'Final_unseen_action_streams.{ext}';fig.savefig(p,dpi=180);outputs.append(p)
        plt.close(fig)
    phase_path=ROOT/'audit/PHASE_DOSE_ATTRIBUTION.json'
    if phase_path.exists():
        phase_cases=json.loads(phase_path.read_text())['cases']
        selected={x['seed']:x for x in phase_cases if x['branch']=='H2_AGG64'
                  and x['endpoint']==30 and x['mode']=='deterministic'
                  and x['same_parent_complete_phase_duration_comparable']}
        if len(selected)==2:
            fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,sharey='row',constrained_layout=True)
            phases=['OUTBOUND','HOLD','RETURN']
            for col,seed in enumerate([1495656323,1630784693]):
                for row,(key,unit) in enumerate([('J_F_N_s','N s'),('J_M_Nm_s','Nm s')]):
                    values=[selected[seed]['difference_from_parent'][p][key] for p in phases]
                    axes[row,col].bar(phases,values,color=['#b85d45' if x>0 else '#387f72' for x in values])
                    axes[row,col].axhline(0,color='black',linewidth=.7)
                    axes[row,col].grid(axis='y',alpha=.25)
                    axes[row,col].set_ylabel(('JF' if row==0 else 'JM')+f' change ({unit})')
                    for i,value in enumerate(values):
                        axes[row,col].annotate(f'{value:+.3f}',(i,value),ha='center',
                            va='bottom' if value>=0 else 'top',fontsize=9,
                            xytext=(0,3 if value>=0 else -3),textcoords='offset points')
                    axes[row,col].margins(y=.22)
                axes[0,col].set_title(f'Seed {seed}, mean after 30 continuations')
            fig.suptitle('H2 phase dose change versus original050: RETURN force decrease with moment tradeoff\nCOMPLETE equal-duration nominal tasks, original 5ms executed-interval metric; no formal matched claim')
            for ext in ['png','pdf']:
                p=ROOT/'TRAINING_CURVES'/f'H2_phase_dose_tradeoff.{ext}';fig.savefig(p,dpi=180);outputs.append(p)
            plt.close(fig)
    atomic(ROOT/'TRAINING_CURVES/MANIFEST.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),
        files=[dict(path=str(p.relative_to(ROOT)),sha256=sha(p)) for p in outputs],branch_to_lineage=lineage_map,
        lineage_evidence='audit/STABILITY_LINEAGE_AUDIT.json',evaluation_split_source='Actual worker EFFECTIVE_CONFIG or original START config; development and heldout actions have distinct marks',
        note='Descriptive development figures. Different reward-scale value losses are not quality rankings. No independent initial-state claim.'))
    print('plotted',len(outputs),'artifacts')
if __name__=='__main__':main()
