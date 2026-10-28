from pathlib import Path
import os,json,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
sys.dont_write_bytecode=True
import numpy as np
import matplotlib.pyplot as plt
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
out=P/'figures';out.mkdir(exist_ok=True)
ids=['HANDOFF01_BEST','STRICT01_REF025','HANDOFF01_BOTHLOW']
names=['Strong fixed','Reference jerk objective (25%)','Anticipatory pass-speed reduction']
colors=['#3d5266','#d28b26','#187f72']
e=[json.loads((P/'analysis/extended'/(i+'.json')).read_text()) for i in ids]
w=[json.loads((P/'analysis/native_wrench'/(i+'.json')).read_text()) for i in ids]
fig,ax=plt.subplots(2,3,figsize=(13,7.4))
metrics=[('Native hip jerk RMS',lambda k:e[k]['native_motion']['jerk_deg_s3']['rms'][0],'degree/s³'),('Native knee jerk RMS',lambda k:e[k]['native_motion']['jerk_deg_s3']['rms'][1],'degree/s³'),('Actual force norm rate RMS (4 kHz)',lambda k:w[k]['force']['norm_rate']['rms'],'N/s'),('Full original JF (5 ms integral)',lambda k:e[k]['JF'],'N s'),('Full original JM (5 ms integral)',lambda k:e[k]['JM'],'Nm s'),('Force vector local fluctuation (100 ms)',lambda k:np.linalg.norm(w[k]['force']['local_linear_residual_100ms']['rms']),'N')]
# Keep the fluctuation field explicit; do not infer a name if the schema differs.
last=w[0]['force']
print('NATIVE_FORCE_KEYS',list(last))
for a,(title,fn,unit) in zip(ax.flat,metrics):
 try:vals=[fn(k) for k in range(3)]
 except KeyError:
  # Show the directly measured force peak if the optional residual schema changes.
  vals=[r['force']['norm']['peak_abs'] for r in w];title='Actual force norm peak (4 kHz)';unit='N'
 a.bar(range(3),vals,color=colors,width=.65)
 a.set_title(title,fontsize=10);a.set_ylabel(unit);a.set_xticks(range(3),['Fixed','Ref smooth','Anticipatory'])
 for k,v in enumerate(vals):a.text(k,v,f'{v:.3f}',ha='center',va='bottom',fontsize=8)
 a.set_ylim(0,max(vals)*1.15);a.grid(axis='y',alpha=.2);a.set_axisbelow(True)
fig.suptitle('Same original action coordinates, full duration, guard and motion gates\nUnfiltered native derivatives; original JF/JM definitions',fontsize=13)
fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(out/'02_VALID_PHYSICAL_TRADEOFF.png',dpi=170);fig.savefig(out/'02_VALID_PHYSICAL_TRADEOFF.pdf');plt.close(fig)
fig,ax=plt.subplots(4,1,figsize=(10,9),sharex=True)
for ident,label,c in [(ids[0],names[0],colors[0]),(ids[2],names[2],colors[2])]:
 with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
  k=np.flatnonzero(z['stage']=='TASK');t=z['time_s'][k];t=t-t[0];ix=(t>=3.05)&(t<=3.23)
  t=t[ix];ref=np.degrees(z['reference_q_rad'][k][ix,1]);v=np.degrees(z['reference_dq_rad_s'][k][ix,1]);tau=z['cr12_actuator_command_nm'][k][ix,1]
  ax[0].plot(t,ref,label=label,color=c,marker='.',ms=3);ax[1].plot(t,v,color=c,marker='.',ms=3);ax[2].plot(t,tau,color=c,marker='.',ms=3)
 with np.load(P/'runtime/motion_series'/(ident+'.npz')) as z:
  t=z['time_s'];t=t-t[0];ix=(t>=3.05)&(t<=3.23);ax[3].plot(t[ix],np.degrees(z['jerk_rad_s3'][ix,1]),color=c,lw=1)
for a in ax:a.grid(alpha=.2)
ax[0].legend(fontsize=8);ax[0].set_ylabel('Knee ref q (deg)');ax[1].set_ylabel('Knee ref dq (deg/s)');ax[2].set_ylabel('Robot joint 2 torque (Nm)');ax[3].set_ylabel('Native knee jerk (deg/s³)');ax[3].set_xlabel('Task time (s)')
fig.suptitle('Actual rolling handoff: held position with nonzero reference velocity\nPass-speed intervention acts before the transient; original executor unchanged',fontsize=12);fig.tight_layout(rect=[0,0,1,.95]);fig.savefig(out/'03_HANDOFF_RAW_MECHANISM.png',dpi=180);fig.savefig(out/'03_HANDOFF_RAW_MECHANISM.pdf');plt.close(fig)
print('FIGURES_WRITTEN')
