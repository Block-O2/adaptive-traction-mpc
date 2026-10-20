from pathlib import Path
import sys,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/force_mechanism_waypoint_v3');sys.path.insert(0,str(P/'control'))
from analyze_mechanism import load,save
B=load('B0');E=load('18D');bounds=B['rec']['task_bounds_s']
fig,axs=plt.subplots(10,1,figsize=(17,21),sharex=True,layout='constrained')
for z,col,name in [(B,'#2166ac','B'),(E,'#b2182b','18D')]:
 axs[0].plot(z['tf'],z['f'],c=col,label=name);axs[1].plot(z['tf'],z['cf'],c=col)
 for j in [0,1]:
  axs[3+j].plot(z['t'],np.degrees(z['v'][:,j]),c=col,label=name+' actual');axs[3+j].plot(z['tf'],np.degrees(z['refv'][:,j]),c=col,ls='--',alpha=.6,label=name+' reference')
 for row,key in [(5,'v'),(6,'a')]:
  cv=np.r_[0,np.cumsum(np.linalg.norm(np.diff(z[key],axis=0),axis=1))];starts=np.arange(0,19.,.05);vals=(np.interp(starts+.05,z['t'],cv)-np.interp(starts,z['t'],cv))/.05;axs[row].plot(starts+.025,vals,c=col)
 axs[7].plot(z['t'][::4],np.linalg.norm(z['j'][::4],axis=1),c=col)
 axs[8].plot(z['tf'],np.linalg.norm(z['q'][::20]-z['refq'],axis=1)*180/np.pi,c=col)
 for kind,mark in [('request','|'),('activation','o'),('splice','x')]:
  ev=[e['task_s'] for e in z['events'] if e['kind']==kind];axs[9].scatter(ev,np.full(len(ev),0 if name=='B' else 1),c=col,marker=mark,label=name+' '+kind,s=35)
axs[2].plot(B['tf'],B['f']-E['f'],c='#238b45',label='Instantaneous force benefit');axs[2].axhline(0,c='.5',lw=.7);axr=axs[2].twinx();axr.plot(B['tf'],B['cf']-E['cf'],c='#762a83',ls='--',label='Accumulated benefit');axr.set_ylabel('B − 18D J_F [N s]')
labels=['Instantaneous force [N]','Cumulative J_F [N s]','B − 18D force [N]','Hip velocity [deg/s]','Knee velocity [deg/s]','Velocity TV rate\n50 ms [rad/s²]','Acceleration TV rate\n50 ms [rad/s³]','Raw jerk norm\n[rad/s³]','Tracking error norm\n[deg]','Lifecycle events']
for ax,lab in zip(axs,labels):
 ax.set_ylabel(lab);ax.set_xlim(0,19.03);ax.grid(alpha=.18)
 for x in bounds[1:-1]:ax.axvline(x,c='.5',lw=.7)
 for lo,hi in [(4,6),(15,16)]:ax.axvspan(lo,hi,color='#238b45',alpha=.09)
 for lo,hi in [(1,2.5),(15,15.5)]:ax.axvspan(lo,hi,color='#d95f02',alpha=.07)
for lo,hi,phase in zip(bounds,bounds[1:],['OUTBOUND','HOLD','RETURN']):axs[0].text((lo+hi)/2,.94,phase,transform=axs[0].get_xaxis_transform(),ha='center',va='top',bbox=dict(facecolor='white',edgecolor='none',alpha=.8),fontsize=10)
axs[0].legend(loc='upper right');axs[2].legend(loc='upper left',fontsize=8);axr.legend(loc='upper right',fontsize=8);axs[3].legend(ncol=4,fontsize=8);axs[9].set_yticks([0,1],['B','18D']);axs[9].legend(ncol=6,fontsize=8);axs[-1].set_xlabel('Task elapsed time [s]');axs[0].secondary_xaxis('top',functions=(lambda x:x+10.05,lambda x:x-10.05)).set_xlabel('Absolute physics time [s]')
fig.suptitle('B vs frozen 18D | one task / absolute time axis\nInstantaneous force = cumulative-force growth rate; green = main benefit windows, orange = high-load windows',fontsize=13);save(fig,'01_core_common_timeline')
print('CORE_REFRESHED')
