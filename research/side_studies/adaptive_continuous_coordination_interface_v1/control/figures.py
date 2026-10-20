"""Static scientific figures from frozen reference payload and raw physics traces."""
from pathlib import Path
import os,json,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR='/tmp/interface_v1_mpl')
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'control'));from audit_physics import sample,polynomial
D=P/'figures';D.mkdir(exist_ok=True);plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130,'savefig.dpi':180})
B='#59677b';N='#007e87';R='#ba4640'
def save(fig,name):
 fig.savefig(D/(name+'.png'),bbox_inches='tight');fig.savefig(D/(name+'.svg'),bbox_inches='tight');plt.close(fig)
def load(n):return json.loads((P/n).read_text())
fig,ax=plt.subplots(figsize=(12,6));ax.set(xlim=(0,12),ylim=(0,6));ax.axis('off')
def box(x,y,w,h,text,color):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.12',fc=color,ec='white'));ax.text(x+w/2,y+h/2,text,ha='center',va='center',color='white',fontsize=10)
box(.2,4.1,2.3,1.1,'Original single quintic\n2 x 6, one duration',B);box(3.1,4.1,2.4,1.1,'Original path certificate\nand escape preparation',B);box(6.2,4.1,2.5,1.1,'Original rolling bridge\n+ certified suffix',B);box(9.4,4.1,2.3,1.1,'Governor / FAST\nallocator / MuJoCo',B)
box(.2,1.6,2.3,1.4,'NEW immutable suffix\n4 x 2 x 6 + knots\nlocal q / dq / ddq',N);box(3.1,1.6,2.4,1.4,'NEW whole-path ID\nC2 / ROM / extrema\ngeometry / model / stop',N);box(6.2,1.6,2.5,1.4,'Original rolling bridge\nNEW current path check\noriginal admission kept',N);box(9.4,1.6,2.3,1.4,'Original execution\n+ receipt evidence\nreference identity',N)
for y in [4.65,2.3]:
 for x in [2.6,5.6,8.8]:ax.annotate('',xy=(x+.4,y),xytext=(x,y),arrowprops={'arrowstyle':'->','lw':1.8,'color':B})
ax.text(.2,5.6,'Minimal isolated extension: two existing source files + one new module',fontsize=14,weight='bold');ax.text(.2,.65,'Geometry: original continuous envelope. Mechanics: original sampled screen + per-piece checks.\nFrozen plant, task, gains, thresholds, lifecycle and physical stepping. No force search.',fontsize=11)
save(fig,'01_interface_architecture')
zero=next(iter(load('output/interface2_zero_multi_REFERENCE_OBJECTS.json')['references'].values()));nz=next(iter(load('output/interface2_knee_002_REFERENCE_OBJECTS.json')['references'].values()));t=np.linspace(0,zero['duration_s'],2001)
z=np.array([sample(zero,float(x),actual=False) for x in t]);o=np.array([polynomial(zero['identity_payload']['original']['values'],zero['duration_s'],float(x)) for x in t]);n=np.array([sample(nz,float(x)) for x in t]);oo=np.array([polynomial(nz['identity_payload']['original']['values'],nz['duration_s'],float(x)) for x in t]);labels=['q (deg)','dq (deg/s)','ddq (deg/s2)']
fig,axs=plt.subplots(3,2,figsize=(10,8),sharex=True)
for k in range(3):
 for j in range(2):
  a=axs[k,j];a.plot(t,np.rad2deg(o[:,k,j]),c=B,lw=2,label='original');a.plot(t,np.rad2deg(z[:,k,j]),'--',c=N,label='actual sub-polynomials');a.set_ylabel(labels[k]);a.grid(alpha=.2)
  a.text(.03,.85,'max error %.2g'%np.max(abs(np.rad2deg(z[:,k,j]-o[:,k,j]))),transform=a.transAxes)
  for x in zero['knots_s'][1:-1]:a.axvline(x,c=B,alpha=.2)
axs[0,0].set_title('Hip');axs[0,1].set_title('Knee');axs[0,0].legend(loc='lower right',fontsize=8)
for a in axs[-1]:a.set_xlabel('local reference time (s)')
fig.suptitle('Zero refinement: exact polynomial identity, independent local-time evaluation');fig.tight_layout();save(fig,'02_zero_reference_equivalence')
fig,axs=plt.subplots(3,2,figsize=(10,8),sharex=True)
for k in range(3):
 axs[k,0].plot(t,np.rad2deg(oo[:,k,1]),c=B,label='original knee');axs[k,0].plot(t,np.rad2deg(n[:,k,1]),'--',c=N,label='modified knee');axs[k,0].set_ylabel(labels[k]);axs[k,1].plot(t,np.rad2deg(n[:,k,1]-oo[:,k,1]),c=N);axs[k,1].set_ylabel('delta '+labels[k]);
 for a in axs[k]:
  a.axvspan(nz['knots_s'][1],nz['knots_s'][3],color=N,alpha=.07);a.grid(alpha=.2)
axs[0,0].legend(fontsize=8);axs[0,0].set_title('Frozen +0.02 degree internal knee position');axs[0,1].set_title('Preserved q/dq/ddq at outer boundaries')
for a in axs[-1]:a.set_xlabel('local reference time (s)')
fig.suptitle('Actual certified nonzero payload; fixed duration and unchanged task anchors');fig.tight_layout();save(fig,'03_internal_control_point_q_dq_ddq')
a=np.load(P/'source/results/interface2_knee_002/trace.npz');b=np.load(P/'source/results/interface2_zero_multi/trace.npz');tm=a['time_s'];start=load('reports/interface2_knee_002_RESPONSE.json')['first_issued_multisegment_physics_s'];ix=(tm>=start-.05)&(tm<=start+nz['duration_s']+.3);offset=load('key_traces/interface2_knee_002/APPLIED_MULTISEGMENT_RECEIPTS.json')['rows'][0]['multisegment_reference']['selected_local_progress_s'];x=tm[ix]-start+offset
fig,axs=plt.subplots(4,1,figsize=(11,9),sharex=True)
for j,c in [(0,B),(1,N)]:
 axs[0].plot(x,np.rad2deg((a['reference_q_rad']-b['reference_q_rad'])[ix,j]),c=c,label=['hip','knee'][j]);axs[1].plot(x,np.rad2deg((a['evaluation_only_human_state_rad_rad_s']-b['evaluation_only_human_state_rad_rad_s'])[ix,j]),c=c);axs[2].plot(x,np.rad2deg((a['evaluation_only_human_state_rad_rad_s']-b['evaluation_only_human_state_rad_rad_s'])[ix,j+2]),c=c)
axs[3].plot(x,np.linalg.norm((a['cr12_actuator_command_nm']-b['cr12_actuator_command_nm'])[ix],axis=1),c=N)
for aa,label in zip(axs,['issued q delta (deg)','actual Human q delta (deg)','actual Human dq delta (deg/s)','robot torque delta norm (Nm)']):
 aa.set_ylabel(label);aa.grid(alpha=.2);aa.axvspan(nz['knots_s'][1],nz['knots_s'][3],color=N,alpha=.07)
axs[0].legend();axs[-1].set_xlabel('local reference time aligned to actual receipt (s)');fig.suptitle('Physical response from identical complete parent: +0.02 degree versus zero multi');fig.tight_layout();save(fig,'04_issued_and_physical_response')
mr=load('PHYSICAL_ARM_RESULTS.json')['rows'];r=next(v for v in mr if v['id']=='interface2_knee_002');old=load('versions/interface1/PHYSICAL_ARM_RESULTS.json')['rows'];bad=next(v for v in old if v['id']=='interface1_knee_005');fig,axs=plt.subplots(3,2,figsize=(12,10));task=a['stage']=='TASK';tx=tm[task]-tm[task][0]
for j,c in [(0,B),(1,N)]:
 axs[0,0].plot(tx,np.rad2deg(a['evaluation_only_human_state_rad_rad_s'][task,j]),c=c,label=['hip','knee'][j]);axs[0,1].plot(tx,np.rad2deg(a['evaluation_only_human_state_rad_rad_s'][task,j+2]),c=c)
for z,col,lab in [(b,B,'zero multi'),(a,N,'+0.02 degree')]:
 axs[1,0].plot(tx,np.linalg.norm(z['physical_cuff_force_world_n'][task],axis=1),c=col,label=lab);axs[1,1].plot(tx,np.linalg.norm(z['physical_cuff_moment_world_nm'][task],axis=1),c=col)
axs[0,0].set_ylabel('Human q (deg)');axs[0,1].set_ylabel('Human dq (deg/s)');axs[1,0].set_ylabel('cuff force norm (N)');axs[1,1].set_ylabel('cuff moment norm (Nm)');axs[0,0].legend();axs[1,0].legend()
for aa in axs[:2].flat:aa.set_xlabel('TASK time (s)');aa.grid(alpha=.2)
keys=list(r['motion']['burden_ratios']);xx=np.arange(len(keys));good=[max(r['motion']['burden_ratios'][k]) for k in keys];fail=[max(bad['motion']['burden_ratios'][k]) for k in keys];axs[2,0].bar(xx-.17,good,.34,color=N,label='.02 PASS');axs[2,0].bar(xx+.17,fail,.34,color=R,label='.05 FAIL');axs[2,0].axhline(1.10,c=R,ls='--',label='frozen limit 1.10');axs[2,0].set_xticks(xx,['v max','v p95','v rms','a max','a p95','a rms','j p95','j rms'],rotation=35,ha='right');axs[2,0].set_ylabel('burden ratio to B (max joint)');axs[2,0].legend(fontsize=8)
m=load('reports/interface2_knee_002_MEASURED.json');ph=['OUTBOUND','HOLD','RETURN'];vals=[m['phase_durations'][p] for p in ph];axs[2,1].bar(ph,vals,color=[B,N,B]);axs[2,1].set_ylabel('phase duration (s)');axs[2,1].set_title('TASK + original motion/fairness PASS')
fig.suptitle('Complete task: physical motion, cuff wrench and unchanged motion gates');fig.tight_layout();save(fig,'05_full_task_force_and_motion')
(P/'figures/PROVENANCE.json').write_text(json.dumps(dict(inputs=['output/interface2_*_REFERENCE_OBJECTS.json','source/results/interface2_*/trace.npz','reports/interface2_*_RESPONSE.json','PHYSICAL_ARM_RESULTS.json','versions/interface1/PHYSICAL_ARM_RESULTS.json'],scope='static scientific figures from actual archived data; no hypothetical physical results'),indent=2));print('FIVE_FIGURES_SAVED')
