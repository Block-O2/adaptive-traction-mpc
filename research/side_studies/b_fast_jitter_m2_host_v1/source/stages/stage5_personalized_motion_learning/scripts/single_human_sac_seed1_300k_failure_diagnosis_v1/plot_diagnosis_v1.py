from inventory_v1 import *
import shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def output(fig,name):
    fig.savefig(L/name,dpi=170);plt.close(fig);shutil.copy2(L/name,D/name)
def run():
    rows=json.loads((D/'NATIVE_TREND_WITH_DISCOUNTED_RETURN.json').read_text());formal=[r for r in rows if r['step']>=50000]
    x=np.array([r['step'] for r in rows])/1000
    fig,axs=plt.subplots(3,2,figsize=(13,11),layout='constrained');a,b,c,d,e,f=axs.ravel()
    a.plot(x,[r['termination_time_s'] for r in rows],'-o',color='#34618c');a.set(title='Failure time',ylabel='Task physics seconds')
    b.plot(x,[r['max_outbound_mean_progress']*100 for r in rows],'-o',label='Max mean clipped joint progress')
    b.plot(x,[r['max_outbound_synchronized_min_progress']*100 for r in rows],'-s',label='Max synchronized min joint progress');b.set(title='Partial OUTBOUND movement',ylabel='Progress (%)',ylim=(-4,105));b.legend(fontsize=8)
    c.plot(x,np.ones(len(x)),'-o',label='Reached phase');c.scatter([225],[1],s=140,facecolors='none',edgecolors='#ae662d',label='225k near goal, no settling')
    c.set(title='Phase reached / acquisition',yticks=[0,1,2,3,4],yticklabels=['Initial','OUTBOUND','HOLD','RETURN','COMPLETE'],ylim=(-.1,4.2));c.legend(fontsize=8,loc='upper left')
    d.plot(x,[r['deterministic_return_offline_estimate'] for r in rows],'-o',label='Undiscounted return')
    d.plot(x,[r['discounted_return_offline_estimate'] for r in rows],'-s',label='Gamma-discounted return');d.set(title='Frozen reward (INVALID tasks)',ylabel='Return, not policy ranking');d.legend(fontsize=8)
    e.plot(x,[r['rejection_rate']*100 for r in rows],'-o',label='Rejected / fallback proposals');e.plot(x,[r['raw_saturation_any_rate']*100 for r in rows],'-s',label='Any joint |raw a| >= .95');e.set(title='Action / safety interaction',ylabel='Policy decisions (%)',ylim=(-4,105));e.legend(fontsize=8)
    f.set(title='Complete VALID J_F ranking only');f.text(.5,.6,'0 / 22 formal evaluations VALID\nNo SAC candidate can be ranked by J_F',ha='center',va='center',transform=f.transAxes,fontsize=13);f.set(xticks=[],yticks=[])
    for ax in (a,b,c,d,e):ax.set_xlabel('Training steps (thousands)');ax.grid(alpha=.2)
    fig.suptitle('Seed 1 failure diagnosis — unchanged R2\nNATIVE shown; MATCHED trajectories are identical until their OUTBOUND failure. Earliest anchor = 12,194, not 10k.',fontsize=13)
    output(fig,'DIAGNOSTIC_TRENDS_V1.png')
    fig,axs=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    for ax,step in zip(axs[0],(225000,300000)):
        with np.load(O/f'paths_{step:07d}_NATIVE_periodic.npz') as z:
            t=z['task_s']
            for j,color in enumerate(('#216294','#bb5a25')):
                ax.plot(t,z['q_est_deg'][:,j],color=color,label=['Hip estimate','Knee estimate'][j]);ax.plot(t,z['reference_deg'][:,j],color=color,linestyle='--',alpha=.65,label=['Hip reference','Knee reference'][j])
            ax.axhline(120,color='#555',linestyle=':',label='Goal120deg');ax.axhline(125,color='#9e2e33',linestyle=':',label='ROM upper125deg');ax.set(title=f'{step//1000}k: OUTBOUND -> Q_BOUNDS',xlabel='Task seconds',ylabel='Joint angle (deg)');ax.grid(alpha=.2);ax.legend(fontsize=7,loc='lower right')
    diag=json.loads((D/'DIAGNOSTIC_fixed_hip_lead_NATIVE.json').read_text())
    with np.load(R/diag['transition_archive']) as z:
        t=z['task_s'];qdeg=z['observations'][:,:2]*125;phase=z['phase']
        for j in range(2):axs[1,0].plot(t,qdeg[:,j],label=['Hip estimate','Knee estimate'][j])
        for p in ('HOLD','RETURN'):
            at=np.flatnonzero(phase==p)
            if len(at):axs[1,0].axvline(t[at[0]],color='#777',linestyle=':');axs[1,0].text(t[at[0]],70,p,rotation=90,ha='right')
    axs[1,0].set(title='Same-wrapper fixed hip-leading: VALID',xlabel='Task seconds',ylabel='Joint angle (deg)');axs[1,0].legend(fontsize=8);axs[1,0].grid(alpha=.2)
    with np.load(O/'paths_0300000_NATIVE_periodic.npz') as z:
        for j,color in enumerate(('#216294','#bb5a25')):
            axs[1,1].plot(z['action_s'],(z['raw_action'][:,j]+1)*62.5,color=color,label=['Raw hip target','Raw knee target'][j])
            axs[1,1].plot(z['action_s'],(z['executed_action'][:,j]+1)*62.5,color=color,linestyle='--',alpha=.6,label=['Executed hip target','Executed knee target'][j])
    axs[1,1].set(title='300k targets: raw = executed, rejection0%',xlabel='Task seconds',ylabel='Absolute target (deg)');axs[1,1].legend(fontsize=7);axs[1,1].grid(alpha=.2)
    fig.suptitle('Moving near the goal is not arriving and settling\n225k closest q=[120.25,119.91]deg, dq=[22.61,36.50]deg/s; task speed tolerance2deg/s.',fontsize=13)
    output(fig,'HIP_KNEE_AND_ACTION_V1.png')
    h=[r for r in json.loads((D/'SAC_HEALTH_SNAPSHOTS.json').read_text()) if 'alpha' in r];x=np.array([r['step'] for r in h])/1000
    fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained')
    axs[0,0].semilogy(x,[r['alpha'] for r in h],'-o');axs[0,0].set(title='Saved entropy coefficient',ylabel='Alpha')
    axs[0,1].plot(x,[r['Q_raw_replay']['mean'] for r in h],'-o');axs[0,1].fill_between(x,[r['Q_raw_replay']['p05'] for r in h],[r['Q_raw_replay']['p95'] for r in h],alpha=.2);axs[0,1].axhline(-1000,color='#666',linestyle=':');axs[0,1].set(title='Frozen Q on identical final-replay states',ylabel='Q mean / 5-95% range')
    axs[1,0].semilogy(x,[r['frozen_sample_critic_loss'] for r in h],'-o');axs[1,0].set(title='Fresh frozen TD-loss estimates (not training logs)',ylabel='Critic loss')
    axs[1,1].bar(['OUTBOUND','HOLD','RETURN'],[100000,0,0],color=['#34618c','#8b8b8b','#8b8b8b']);axs[1,1].set(title='Final replay phase coverage',ylabel='Transitions');axs[1,1].text(.95,.5,'No success reward\nNo HOLD / RETURN',transform=axs[1,1].transAxes,ha='right',fontsize=10)
    for ax in list(axs.ravel())[:3]:ax.set_xlabel('Checkpoint steps (thousands)');ax.grid(alpha=.2)
    fig.suptitle('Optimization audit: finite parameters / Adam state; failure-dominated data\n4096 shared final-replay samples; early checkpoints see later/OOD states. Historical loss time series was not saved.',fontsize=12)
    output(fig,'SAC_HEALTH_V1.png');shutil.copy2(Path(__file__),P/Path(__file__).name)
if __name__=='__main__':run()
