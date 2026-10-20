from pathlib import Path
import os,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_early_return_motion_repair_v1')
def main():
 summary=json.loads((S/'SEARCH_SUMMARY.json').read_text());rows=[json.loads(r) for r in (S/'RESULTS.jsonl').read_text().splitlines()];dis=[r for r in rows if r['id'].startswith('discovery_') and r['stage'] in ['C1','C2','C3','C4','REFERENCE']];best=summary['representatives']['best_eligible'] or summary['representatives']['lowest_J_F']
 fig,ax=plt.subplots(2,2,figsize=(12,8),constrained_layout=True)
 for stage,marker in [('C1','o'),('C2','s'),('C3','^'),('C4','D'),('REFERENCE','X')]:
  rr=[r for r in dis if r['stage']==stage]
  for accepted,color in [(False,'#a3a8af'),(True,'#16856a')]:
   p=[r for r in rr if r['comparison']['acceptance_pass']==accepted]
   if not p:continue
   ax[0,0].scatter([max(r['comparison']['burden_ratios']['acceleration_deg_s2/p95_abs']) for r in p],[r['comparison']['gain_percent'] for r in p],c=color,marker=marker,s=35,alpha=.75,label=f'{stage} motion {"PASS" if accepted else "FAIL"}')
 ax[0,0].axhline(.5,color='#3365a3',ls='--',lw=1);ax[0,0].axvline(1.1,color='#ab4b37',ls='--',lw=1);ax[0,0].set(xlabel='Max hip/knee p95 acceleration / B',ylabel='Full task force-integral gain (%)',title='Actual native force and motion');ax[0,0].legend(fontsize=6,ncol=2)
 counts=summary['counts_by_stage'];ax[0,1].bar(list(counts),list(counts.values()),color='#547ca4');ax[0,1].set(ylabel='Measured candidates',title=f'Attempt denominator {summary["attempt_denominator"]} / 160')
 if best:
  for ident,label,color in [('discovery_B0_repeat_1','B','#344054'),(best['id'],best['candidate_id'],'#16856a')]:
   with np.load(S/'motion_series'/(ident+'.npz')) as z:
    t=z['time_s']-z['time_s'][0];v=np.rad2deg(z['true_dq_rad_s'][:,1]);a=np.rad2deg(z['acceleration_rad_s2'][:,1]);stride=20
    ax[1,0].plot(t[::stride],v[::stride],label=label,color=color,lw=1)
    ax[1,1].plot(t[::stride],a[::stride],label=label,color=color,lw=.8)
 ax[1,0].set(xlabel='TASK time (s)',ylabel='True knee velocity (deg/s)',title='Frozen representative vs B');ax[1,0].legend(fontsize=8)
 ax[1,1].set(xlabel='TASK time (s)',ylabel='True knee acceleration (deg/s²)',title='Display decimated; metrics use all native samples');ax[1,1].legend(fontsize=8)
 for a in ax.flat:a.grid(alpha=.15)
 fig.suptitle('Scientific matched execution • research acceptance • no host-clock qualification',fontsize=11)
 fig.savefig(S/'FORCE_MOTION_SEARCH.png',dpi=160);fig.savefig(S/'FORCE_MOTION_SEARCH.svg');plt.close(fig)
if __name__=='__main__':main()
