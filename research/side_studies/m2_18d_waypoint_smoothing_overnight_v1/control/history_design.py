"""Recompute historical evidence and register bounded motion-directed shapes."""
from pathlib import Path
import os,sys,json,hashlib,time,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'control'),str(P/'code')]
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import minimize
from analyze_mechanism import load,metrics,put,integ,sha
import study_common
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import hermite
B=load('B0');E=load('18D');cases={'B':B,'E':E}
files={}
for tag,z in cases.items():
 run=Path(z['rec']['source_root'])/'source/results'/z['rec']['archive_case']
 for f in [run/'trace.npz',run/'summary.json',run/'runtime_artifacts.json.gz',run/'config_snapshot.json']:
  files[str(f)]={'sha256':sha(f),'bytes':f.stat().st_size}
 np.savez_compressed(P/'series'/('historical_'+tag+'.npz'),**{k:v for k,v in z.items() if isinstance(v,np.ndarray)})
put('audit/HISTORICAL_INPUTS.json',files)
win=[(0,19.03),(0,9.005),(9.005,10.025),(10.025,19.03),(4,6),(15,16),(15,15.5),(15.5,16),(1,2.5)]
mm={f'{lo:g}-{hi:g}':{tag:metrics(z,lo,hi) for tag,z in cases.items()} for lo,hi in win}
put('derived/HISTORICAL_WINDOWS.json',mm)
bf=float(integ(B['tf'],B['f'],0,B['tf'][-1]));ef=float(integ(E['tf'],E['f'],0,E['tf'][-1]))
assert abs(bf-1438.613498467)<1e-8 and abs(ef-1400.697221153)<1e-8
put('BASELINE_REPRODUCTION.json',dict(status='ARCHIVAL_RECALCULATION_PASS_NEW_PHYSICS_PENDING',B=bf,E18D=ef,gain=bf-ef,gain_percent=100*(bf-ef)/bf,force_sample_period_s=.005,motion_sample_period_s=.00025,method='full original TASK left integral; no physics run',windows=mm))
fig,axs=plt.subplots(13,1,figsize=(16,27),sharex=True,layout='constrained')
for tag,z in cases.items():
 co='#2166ac' if tag=='B' else '#b2182b';label='B' if tag=='B' else '18D'
 axs[0].plot(z['tf'],z['f'],c=co,label=label);axs[1].plot(z['tf'],z['cf'],c=co)
 for j in range(2):
  axs[2+j].plot(z['t'][::10],np.degrees(z['q'][::10,j]),c=co);axs[2+j].plot(z['tf'],np.degrees(z['refq'][:,j]),c=co,ls='--',alpha=.6)
  axs[4+j].plot(z['t'][::10],np.degrees(z['v'][::10,j]),c=co,label=label+' actual');axs[4+j].plot(z['tf'],np.degrees(z['refv'][:,j]),c=co,ls='--',alpha=.6,label=label+' reference')
 axs[6].plot(z['t'][::10],np.linalg.norm(z['a'][::10],axis=1),c=co)
 axs[7].plot(z['t'][::10],np.linalg.norm(z['j'][::10],axis=1),c=co)
 axs[8].plot(z['tf'],np.linalg.norm(z['q'][::20]-z['refq'],axis=1)*180/np.pi,c=co)
 axs[9].plot(z['tf'],np.linalg.norm(z['torque'],axis=1),c=co)
 axs[10].plot(z['tf'],np.linalg.norm(z['robot_torque_component_allocator_nm'],axis=1),c=co)
 axs[11].plot(z['tf'],np.linalg.norm(z['physical_cuff_moment_world_nm'],axis=1),c=co)
 for k,mark,y in [('request','|',0),('activation','o',.2),('splice','x',.4)]:
  es=[e['task_s'] for e in z['events'] if e['kind']==k];axs[12].scatter(es,np.full(len(es),y+(0 if tag=='B' else 1)),c=co,marker=mark,s=20,label=label+' '+k)
labels=['Force [N], 5 ms','Cumulative J_F [N s]','Hip q [deg]','Knee q [deg]','Hip v [deg/s]','Knee v [deg/s]','Acceleration norm [rad/s²]','Raw jerk norm [rad/s³]','Tracking norm [deg]','Robot torque norm [Nm]','Allocator torque norm [Nm]','Cuff moment [Nm]','Events']
for ax,lab in zip(axs,labels):
 ax.set_ylabel(lab);ax.grid(alpha=.2);ax.set_xlim(0,19.03)
 for t in [9.005,10.025]:ax.axvline(t,c='.4',lw=.7)
 for a,b in [(4,6),(15,16)]:ax.axvspan(a,b,color='green',alpha=.05)
axs[0].legend();axs[4].legend(ncol=4);axs[12].legend(ncol=6);axs[-1].set_xlabel('Task elapsed [s]; absolute physics time = task + 10.05 s')
fig.suptitle('Historical B vs exact 18D | archived data, no new physics | solid actual, dashed reference')
fig.savefig(P/'figures/18d_mechanism_timeline.png',dpi=150);plt.close(fig)
frozen=json.loads((P/'provenance/18D_FROZEN_SELECTION.json').read_text())['best']['candidate'];put('HISTORICAL_18D_PARAMETERS.json',frozen)
designs=[]
def poly(c,u,T,d=0):return np.array([np.polynomial.polynomial.polyval(np.atleast_1d(u),np.polynomial.polynomial.polyder(row,d)) for row in c]).T/T**d
for tag,z in cases.items():
 counts={}
 for lr in z['su']['learning_records']:
  d=z['su']['decisions'][lr['decision_index']];ph=d['phase'];slot=counts.get(ph,0);counts[ph]=slot+1
  if (ph,slot) not in [('OUTBOUND',3),('RETURN',3)]:continue
  sch=lr['selected_plan']['schedule'];T=sch['duration_s'];co=np.asarray(hermite(np.asarray(sch['start_q_rad']),np.asarray(sch['start_dq_rad_s']),np.zeros(2),np.asarray(sch['target_q_rad']),np.asarray(sch['target_dq_rad_s']),np.zeros(2),T))
  fs=np.array([0,.2,.4,.8,1]);states=[[poly(co,u,T,k)[0] for k in range(3)] for u in fs]
  def vel(x):
   ss=[[v.copy() for v in a] for a in states]
   for i,de in enumerate(np.radians(np.asarray(x).reshape(3,2))):ss[i+1][0]+=de
   return np.vstack([poly(np.asarray(hermite(*ss[i],*ss[i+1],T*(fs[i+1]-fs[i]))),np.linspace(0,1,201),T*(fs[i+1]-fs[i]),1) for i in range(4)])
  def objective(x):return float(np.linalg.norm(np.diff(vel(x),axis=0),axis=1).sum())
  opt=minimize(objective,np.zeros(6),method='SLSQP',bounds=[(-.05,.05)]*6,options={'maxiter':120,'ftol':1e-12});assert opt.success
  start=d['decision_request_time_s']-10.05+.05
  designs.append(dict(id=tag+('_O' if ph=='OUTBOUND' else '_R'),base=tag,phase=ph,slot=3,decision_index=lr['decision_index'],local_window_task_s=[start,start+T],spec=dict(fractions=fs[1:-1].tolist(),deltas_deg=opt.x.reshape(3,2).tolist()),reference_TV_baseline=objective(np.zeros(6)),reference_TV_smooth=objective(opt.x),duration_s=T,archived_schedule=sch,offline_optimization=dict(method='SLSQP reference velocity TV only',nfev=opt.nfev,success=opt.success)))
coarse=[dict(id='B0',base='B',changes=[]),dict(id='E0',base='E',changes=[])]
for base in ['B','E']:
 ds=[d for d in designs if d['base']==base]
 coarse.append(dict(id=base+'_zero',base=base,changes=[{**d,'spec':{**d['spec'],'deltas_deg':np.zeros((3,2)).tolist()}} for d in ds]))
 for d in ds:
  for label,scale in [('smooth',1),('opposite',-.25)]:
   coarse.append(dict(id=d['id']+'_'+label,base=base,changes=[{**d,'spec':{**d['spec'],'deltas_deg':(np.asarray(d['spec']['deltas_deg'])*scale).tolist()}}]))
put('CANDIDATE_PLAN.json',dict(frozen_unix=time.time(),designs=designs,coarse=coarse,conditionals='Only if original gates pass AND actual local TV falls >=0.5% AND local force falls: one half amplitude, one repeat; combine O+R only if both individually pass. At most one additional motion-directed refinement per informative window. Stop direction after 3-5 uninformative candidates. No random sweep.',four_group_interpretation='base-specific motion-directed optimizer; fixed-delta crossover required before claiming interaction of identical interventions'))
put('EXECUTABLE_PLAN.json',dict(coarse=coarse,offline_certificate_status='PENDING',runtime_certificate_required=True))
(P/'HISTORICAL_18D_MECHANISM.md').write_text('''# Historical 18D mechanism audit

本轮从原始 trace 独立复算：B=1438.613498467 N·s，18D=1400.697221153 N·s；两者完整任务19.030 s。开发条件既有 task/safety/motion PASS；历史合法新prefix motion仍为0/4，未获得正式Native LEVEL2、host-clock LEVEL3、真机或临床资格。

18D不是18个任意waypoint。`rich_planner.py`在原NativeResidualPlannerV2上加入18个连续参数：OUT/RETURN各相位的common/differential progress多项式，以及通过速度的common/differential tilt。先使用原生目标计算归一化进度m、e=sin²(pi*m)、u=2m−1，再改变内部目标；原scheduler选择合法duration并认证。完整方案还包含RETURN槽1/2的−0.020/−0.022 differential plateau；遗漏这两项就不再是原18D。完整参数保存于HISTORICAL_18D_PARAMETERS.json；组合必须保留它们。

4–6 s降力10.099746 N·s，TV_v下降，但TV_a与combined jerk RMS增加。15–16 s降力9.996502 N·s，TV_v与combined jerk RMS下降，TV_a增加；其中15–15.5 s甚至TV_v、TV_a与jerk同时变差。不能把18D当成单纯平滑成功案例。

既有v3存档机制核算给出：原allocator代数输入重算净变化−36.527540 N·s，实测−37.916277 N·s；去程更早抬髋与模型重力需求下降一致，回程更早降膝与弹性需求下降一致。相同commissioned参数下，geometry单独作用并不占优。command分量重构显示allocator通道差异最大，但这是代数分解，不是关闭通道后的物理反事实。上述分解作为有来源的既有证据保留，本轮不冒称重新执行其完整kinematic重构。

tracking并非全部改善，完整moment积分增加约7.03%。request/splice时序也发生变化，RETURN slot4的splice提前约0.405 s。姿态负荷、tracking、allocator和时序共同变化；尚不能唯一归因于smoothness、某一torque通道或时间调度。新干预只改变内部q点，保留每个外端q/dq/ddq与suffix duration，整任务duration与phase边界另以实际结果核验。

原始来源hash：audit/HISTORICAL_INPUTS.json。逐窗独立指标：derived/HISTORICAL_WINDOWS.json。共同时间轴：figures/18d_mechanism_timeline.png。瞬时force为5ms存档采样；native motion为0.25ms，不能混称force采样率。
''',encoding='utf-8')
print('HISTORICAL_AUDIT_AND_DESIGN_SAVED',bf,ef,len(designs))
