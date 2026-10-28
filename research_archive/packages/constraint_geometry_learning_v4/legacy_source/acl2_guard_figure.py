"""Export the observed original-guard computation and unfiltered native burst."""
import numpy as np
from acl2_shared import P,R,read

def main():
    f=P/'audit/ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json'
    if not f.exists():return
    d=read('audit/ORIGINAL_CLEARANCE_GUARD_CUSP_REPLAY.json');ident=d['attempt_id'];origin=d['causal_source_sample_s']
    import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
    fig,ax=plt.subplots(2,2,figsize=(12,8))
    with np.load(R/'source/results'/ident/'trace.npz') as z:
        mask=abs(z['time_s']-origin)<.035;t=1000*(z['time_s'][mask]-origin);x=z['estimated_human_state_rad_rad_s'][mask];q=z['reference_q_rad'][mask];ax[0,0].plot(t,np.degrees(x[:,0]-x[:,1]),'o-',label='Causal estimated hip-knee');ax[0,0].plot(t,np.degrees(q[:,0]-q[:,1]),'--',label='Issued reference hip-knee')
    ax[0,0].axhline(0,color='grey',linewidth=.7);ax[0,0].set(xlabel='Time relative to guard command (ms)',ylabel='Hip minus knee (deg)');ax[0,0].legend(fontsize=8)
    s=d['stencil_sweep'];ax[0,1].semilogx([r['time_stencil_s'] for r in s],[r['curvature_m_s2'] for r in s],'o-');ax[0,1].axvline(1e-5,color='red',linestyle='--',label='Original stencil: 10 us');ax[0,1].set(xlabel='Diagnostic time stencil (s)',ylabel='Nominal sleeve curvature (m/s^2)',title='Crossing a nonsmooth envelope branch');ax[0,1].legend(fontsize=8)
    with np.load(R/'motion_series'/(ident+'.npz')) as z:
        mask=abs(z['time_s']-origin)<.035;t=1000*(z['time_s'][mask]-origin)
        for j,name in enumerate(['Hip','Knee']):
            ax[1,0].plot(t,np.degrees(z['acceleration_rad_s2'][mask,j]),label=name);ax[1,1].plot(t,np.degrees(z['jerk_rad_s3'][mask,j]),label=name)
    ax[1,0].set(xlabel='Time relative to guard command (ms)',ylabel='Raw native acceleration (deg/s^2)');ax[1,1].set(xlabel='Time relative to guard command (ms)',ylabel='Raw native jerk (deg/s^3)')
    for a in ax[1]:a.axvline(0,color='grey',linestyle='--');a.legend(fontsize=8)
    for a in ax.flat:a.grid(alpha=.2)
    fig.suptitle('CORE_C_019: unchanged original guard; generalized correction [14.915, -4.409] Nm\nPosthoc causal-input replay and native measurements; no guard removed',fontsize=11);fig.tight_layout();fig.savefig(P/'figures/CLEARANCE_GUARD_NATIVE_BURST.png',dpi=170);fig.savefig(P/'figures/CLEARANCE_GUARD_NATIVE_BURST.pdf');plt.close(fig)

if __name__=='__main__':main()
