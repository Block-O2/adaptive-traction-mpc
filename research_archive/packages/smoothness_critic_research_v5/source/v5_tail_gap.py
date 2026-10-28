from pathlib import Path
import os,sys,json,datetime
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg');sys.dont_write_bytecode=True
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
fig,axs=plt.subplots(1,2,figsize=(12,4.5));records=[]
for group,short,full,ax in [('TAILO1','SPEEDP','RELATIVEP',axs[0]),('TAILR1','SPEEDM','RELATIVEM',axs[1])]:
 fork=json.loads((P/'audit'/(group+'_FORK_CONTEXT.json')).read_text())['physical_s'];series=[]
 for tag in [short,full]:
  with np.load(P/'runtime/source/results'/(group+'_'+tag)/'trace.npz') as z:
   k=z['stage']=='TASK';t=z['time_s'][k];force=np.linalg.norm(z['physical_cuff_force_world_n'][k],axis=1)
  widths=np.maximum(0,t[1:]-np.maximum(t[:-1],fork));cost=np.r_[0,np.cumsum(force[:-1]*widths)];use=t>=fork-1e-9;series.append((t[use]-fork,cost[use]))
 assert np.max(abs(series[0][0]-series[1][0]))<1e-9,'PAIRED_PHYSICAL_TIME_IDENTITY'
 t=series[0][0];gap=series[0][1]-series[1][1];end=float(gap[-1]);tol=max(.005,abs(end)*.05);tailerr=np.maximum.accumulate(abs(gap-end)[::-1])[::-1];settled=np.flatnonzero(tailerr<=tol)
 H=[.25,.5,1.];hvals=[float(np.interp(h,t,gap)) for h in H]
 ax.plot(t,gap,color='#245c83',lw=1.6);ax.axhline(0,color='#555',lw=.8)
 for h,v in zip(H,hvals):ax.axvline(h,color='#999',lw=.6,ls=':');ax.scatter([h],[v],s=25)
 ax.set_title(group+': '+short+' minus '+full);ax.set_xlabel('Time after same-state fork (s)');ax.set_ylabel('Cumulative original JF difference (N s)');ax.grid(alpha=.2)
 ax.text(.97,.08,f'Full difference: {end:.6f} N s',ha='right',transform=ax.transAxes)
 rec=dict(group=group,short_candidate=group+'_'+short,full_candidate=group+'_'+full,horizons_s=H,cumulative_short_minus_full_JF_at_horizons=hvals,complete_JF_regret_N_s=end,final_gap_tolerance_N_s=tol,earliest_time_after_which_all_later_gaps_within_tolerance_s=None if not len(settled) else float(t[settled[0]]),full_remaining_duration_s=float(t[-1]),source='Actual full rolling continuation traces, original 5ms left integration; common state and following B policy. Time-to-settle is descriptive, not a new controller horizon guarantee.')
 records.append(rec)
fig.suptitle('Observed myopia is a transient candidate-ranking effect\nActual full tail is an offline reference, not a globally optimal oracle',fontsize=12);fig.tight_layout(rect=[0,0,1,.9]);fig.savefig(P/'figures/04_ACTUAL_ROLLING_TAIL_GAP.png',dpi=180);fig.savefig(P/'figures/04_ACTUAL_ROLLING_TAIL_GAP.pdf');plt.close(fig)
(P/'analysis/C1_TEMPORAL_COST_GAP.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),rows=records,new_native_steps=0),indent=2)+'\n')
for r in records:print(r['group'],'gap at H',r['cumulative_short_minus_full_JF_at_horizons'],'full',r['complete_JF_regret_N_s'],'settled',r['earliest_time_after_which_all_later_gaps_within_tolerance_s'])
