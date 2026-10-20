"""Closed-loop factorial contrasts; observation timing is not a unique causal decomposition."""
from pathlib import Path
import os,sys,json
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def first(t,a,b):
    q=np.asarray(a)!=np.asarray(b);q=q.reshape(len(q),-1).any(1);ix=np.flatnonzero(q)
    return float(t[ix[0]]) if len(ix) else None
out=[]
for g in sys.argv[1:]:
    for a,b in [('HIP','ZERO'),('KNEE','ZERO'),('H150','KNEE'),('H150','HIP')]:
        za=np.load(P/'source/results'/(g+'_'+a)/'trace.npz');zb=np.load(P/'source/results'/(g+'_'+b)/'trace.npz')
        mask=za['stage']=='TASK';mb=zb['stage']=='TASK';ta=za['time_s'][mask];tb=zb['time_s'][mb];assert np.array_equal(ta,tb)
        t=ta-ta[0];keys=['reference_q_rad','reference_dq_rad_s','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','cr12_actuator_command_nm','physical_cuff_force_world_n','physical_cuff_moment_world_nm']
        changes={k:first(t,za[k][mask],zb[k][mb]) for k in keys}
        rq=za['reference_q_rad'][mask]-zb['reference_q_rad'][mb];true=za['evaluation_only_human_state_rad_rad_s'][mask]-zb['evaluation_only_human_state_rad_rad_s'][mb]
        before=t<changes['reference_q_rad']-1e-9
        out.append(dict(parent=g,contrast=a+' minus '+b,first_difference_task_s=changes,pre_reference_intervention_all_trace_fields_equal=all(np.array_equal(za[k][mask][before],zb[k][mb][before]) for k in keys),max_reference_angle_difference_deg=np.rad2deg(np.max(abs(rq),axis=0)).tolist(),max_true_human_angle_difference_deg=np.rad2deg(np.max(abs(true[:,:2]),axis=0)).tolist(),interpretation='total closed-loop effect of the registered reference intervention; later original replanning can change other-joint reference, so not a pure passive mechanical coupling coefficient',sampling_resolution_s=.005))
(P/'derived/COUPLED_FACTORIAL_CONTRASTS.json').write_text(json.dumps(dict(rows=out,unique_robot_cuff_Human_delay_identified=False,causal_ingredients_separated=False),indent=2)+'\n')
g=sys.argv[1];fig,axs=plt.subplots(3,1,figsize=(11,10),sharex=True,layout='constrained')
for a in ['B','H150','HIP','KNEE','ZERO']:
    z=np.load(P/'source/results'/(g+'_'+a)/'trace.npz');mask=z['stage']=='TASK';t=z['time_s'][mask];t=t-t[0]
    axs[0].plot(t,np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][mask,1]),label=a)
    axs[1].plot(t,np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1),label=a)
    axs[2].plot(t,np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1),label=a)
for ax,lab in zip(axs,['Actual knee (deg)','Cuff force (N)','Cuff moment (Nm)']):ax.set_ylabel(lab);ax.grid(alpha=.25)
axs[0].legend(ncol=5);axs[-1].set_xlabel('Task time (s)');fig.savefig(P/'figures/01_control_motion_force.png',dpi=170);plt.close(fig)
fig,ax=plt.subplots(figsize=(13,5),layout='constrained');ax.axis('off')
labels=['Causal estimates\n+ prior feedback\n(if available)','Frozen / learned\nbounded reference\nchoice','Original B planner\ncertificate\n+ admission','Robot controller\nallocator + cuff\n+ passive Human','Actual receipts\n+ full-task\noutcomes']
positions=[(.1,.60),(.3,.60),(.5,.60),(.7,.60),(.9,.60)]
for (x,y),label in zip(positions,labels):ax.text(x,y,label,ha='center',va='center',fontsize=9,bbox=dict(boxstyle='round,pad=.65',fc='#e7f0f7',ec='#236080'),transform=ax.transAxes)
for i in range(4):ax.annotate('',xy=(positions[i+1][0]-.08,.6),xytext=(positions[i][0]+.08,.6),xycoords='axes fraction',arrowprops=dict(arrowstyle='->',lw=1.8))
ax.text(.5,.25,'Offline only: native truth, matched-B motion labels, qualification and cost comparison\nNo future truth or future matched-B statistics in online features',ha='center',va='center',fontsize=11,transform=ax.transAxes)
ax.annotate('',xy=(.1,.45),xytext=(.9,.45),xycoords='axes fraction',arrowprops=dict(arrowstyle='->',lw=1.5))
ax.text(.5,.40,'Measured completed-task feedback (only when actually enabled)',ha='center',va='center',fontsize=9,transform=ax.transAxes)
fig.savefig(P/'figures/05_learning_structure.png',dpi=170);plt.close(fig)
print('COUPLED_CONTRASTS_COMPLETE',len(out),flush=True)
