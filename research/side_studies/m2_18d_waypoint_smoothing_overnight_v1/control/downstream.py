"""Split local versus downstream observed effects, without causal overclaim."""
from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'control'),str(P/'code')]
from postprocess_targeted import load
from analyze_mechanism import put,integ
import numpy as np
import matplotlib.pyplot as plt
rs=json.loads((P/'ALL_ANALYZED_RESULTS.json').read_text())['rows'];out=[];fig,axs=plt.subplots(3,2,figsize=(16,12),sharex=True,layout='constrained')
for r in rs:
 if r['status']!='COMPLETE' or not r['candidate'].get('changes') or r['candidate']['id'].endswith('_zero'):continue
 z=load(r['id']);b=load(r['matched_baseline']);end=z['tf'][-1]
 if z['tf'].shape!=b['tf'].shape:continue
 diff=z['f']-b['f'];cumulative=z['cf']-b['cf'];intervals=[c['local_window_task_s'] for c in r['candidate']['changes']];local=sum(float(integ(z['tf'],diff,*iv)) for iv in intervals)
 cutoff=max(iv[1] for iv in intervals);snapshots={str(t):float(np.interp(t,z['tf'],cumulative)) for t in sorted(set([0.,*sum(intervals,[]),min(cutoff+.5,end),min(cutoff+1,end),9.005,10.025,float(end)]))}
 out.append(dict(id=r['id'],support_delta_N_s=local,outside_support_delta_N_s=float(cumulative[-1])-local,full_delta_N_s=float(cumulative[-1]),after_last_support_delta_N_s=float(integ(z['tf'],diff,cutoff,end)),cumulative_snapshots=snapshots,schedule_changes=r['schedule_changes'],full_velocity_TV_change_percent=r['full_TV_v_change_percent'],warning='outside/support are accounting intervals, not identified independent causal mediators'))
 col=0 if r['candidate']['base']=='B' else 1
 if r['candidate']['id'].endswith(('_smooth','_half')):
  line=axs[0,col].plot(z['tf'],diff,label=r['candidate']['id'])[0];co=line.get_color();axs[1,col].plot(z['tf'],cumulative,c=co)
  av=np.linalg.norm(np.diff(z['v'],axis=0),axis=1);bv=np.linalg.norm(np.diff(b['v'],axis=0),axis=1);axs[2,col].plot(z['t'][1:][::20],(np.cumsum(av)-np.cumsum(bv))[::20],c=co)
for col,label in enumerate(['B','18D']):
 axs[0,col].set_title(label+' interventions');axs[0,col].legend(fontsize=7,ncol=2);axs[0,col].set_ylabel('Force − matched base [N]');axs[1,col].set_ylabel('Cumulative ΔJ_F [N s]');axs[2,col].set_ylabel('Cumulative Δvelocity TV [rad/s]');axs[2,col].set_xlabel('Task elapsed [s]')
 for ax in axs[:,col]:
  ax.axhline(0,c='.5',lw=.7);ax.grid(alpha=.2)
  for t in [9.005,10.025]:ax.axvline(t,c='.5',lw=.7)
fig.suptitle('Local effects can be offset downstream | original task clock, no peak alignment');fig.savefig(P/'figures/downstream_cumulative_effects.png',dpi=160);plt.close(fig)
put('derived/DOWNSTREAM_ACCOUNTING.json',dict(rows=out,physics_starts=0))
print('DOWNSTREAM_CASES',len(out))
