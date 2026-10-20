"""Independent raw arithmetic and certificate reconstruction; zero physics."""
from pathlib import Path
import os,sys,json,hashlib,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'control'),str(P/'code')]
import numpy as np
import matplotlib.pyplot as plt
from postprocess_targeted import load,audit
from analyze_mechanism import put,metrics,integ,clean
assert 'study_common' not in sys.modules,'Analysis must not load physics entry'
def motion(z,lo,hi):
 ix=(z['t']>=lo-1e-8)&(z['t']<=hi+1e-8);v=z['v'][ix];a=z['a'][ix];j=z['j'][ix];q=z['q'][ix]
 return dict(velocity_TV=float(np.linalg.norm(np.diff(v,axis=0),axis=1).sum()),velocity_TV_joint=abs(np.diff(v,axis=0)).sum(axis=0),speed_variation=float(abs(np.diff(np.linalg.norm(v,axis=1))).sum()),speed_variation_joint=abs(np.diff(abs(v),axis=0)).sum(axis=0),acceleration_variation=float(np.linalg.norm(np.diff(a,axis=0),axis=1).sum()),acceleration_variation_joint=abs(np.diff(a,axis=0)).sum(axis=0),jerk_RMS=np.sqrt(np.mean(j*j,axis=0)),jerk_p95=np.quantile(abs(j),.95,axis=0),jerk_max=abs(j).max(axis=0),combined_jerk_RMS=float(np.sqrt(np.mean(np.sum(j*j,axis=1)))),combined_jerk_p95=float(np.quantile(np.linalg.norm(j,axis=1),.95)),combined_jerk_max=float(np.linalg.norm(j,axis=1).max()),joint_travel_deg=np.degrees(abs(np.diff(q,axis=0)).sum(axis=0)),excursion_deg=np.degrees(np.ptp(q,axis=0)))
def analyze():
 rows=[json.loads(l) for l in (P/'EXPLORATION_RESULTS.jsonl').read_text().splitlines()];zs={};out=[]
 for r in rows:
  if r['status']!='COMPLETE':out.append(r);continue
  ident=r['id'];z=load(ident);zs[ident]=z;ar=audit(ident,z);base=r['matched_baseline']
  if base not in zs:zs[base]=load(base)
  b=zs[base];end=float(z['tf'][-1]);wm={}
  for lo,hi in [(0,end),(0,9.005),(9.005,10.025),(10.025,end),(4,6),(15,16)]+[tuple(c['local_window_task_s']) for c in r['candidate'].get('changes',[])]:
   w=metrics(z,lo,hi);w.update(motion(z,lo,hi));w['force_RMS']=float(np.sqrt(integ(z['tf'],z['f']**2,lo,hi)/(hi-lo)));wm[f'{lo:.6f}-{hi:.6f}']=w
  full=motion(z,0,end);basefull=motion(b,0,float(b['tf'][-1]));m=json.loads((P/'reports'/(ident+'_MEASURED.json')).read_text())
  assert abs(float(integ(z['tf'],z['f'],0,end))-r['J_F'])<1e-8
  assert np.max(abs(np.gradient(z['v'],z['t'],axis=0,edge_order=2)-z['a']))<1e-7
  record=dict(**r,independent_audit=ar,windows=wm,full_motion=full,matched_full_motion=basefull,full_TV_v_change_percent=100*(full['velocity_TV']/basefull['velocity_TV']-1),full_jerk_change_percent=100*(full['combined_jerk_RMS']/basefull['combined_jerk_RMS']-1),full_J_F_delta=r['J_F']-float(b['cf'][-1]),duration=end,phase_cost=m['phase_cost'],dose=m['dose'],tracking_RMS_deg=m['tracking_RMS_deg'])
  if len(z['tf'])==len(b['tf']) and np.max(abs(z['tf']-b['tf']))<1e-8:
   record['actual_max_q_deviation_deg']=np.degrees(abs(z['q']-b['q']).max(axis=0));record['actual_max_dq_deviation_deg_s']=np.degrees(abs(z['v']-b['v']).max(axis=0));record['reference_max_deviation_deg']=np.degrees(abs(z['refq']-b['refq']).max(axis=0))
   record['full_positive_force_difference_area']=float(integ(z['tf'],np.maximum(z['f']-b['f'],0),0,end));record['full_negative_force_difference_area']=float(integ(z['tf'],np.minimum(z['f']-b['f'],0),0,end))
   first=ar['first_multisegment_task_s']
   if first is not None:
    before=z['tf']<first-1e-8;record['pre_intervention_exact']={k:bool(np.array_equal(z[k][before],b[k][before],equal_nan=True)) for k in ['f','refq','refv','torque','evaluation_only_human_state_rad_rad_s','cr12_q_rad','physical_cuff_moment_world_nm']};assert all(record['pre_intervention_exact'].values()),'PRE_INTERVENTION_DIFFERENCE'
  original=[d for d in b['su']['decisions']];record['schedule_changes']=[dict(index=i,baseline_request_s=y['decision_request_time_s'],candidate_request_s=x['decision_request_time_s'],baseline_label=y['executed_label'],candidate_label=x['executed_label']) for i,(x,y) in enumerate(zip(z['su']['decisions'],original)) if x['decision_request_time_s']!=y['decision_request_time_s'] or x['executed_label']!=y['executed_label']]
  put('derived/'+ident+'_METRICS.json',record);out.append(record)
  np.savez_compressed(P/'series'/(ident+'.npz'),**{k:v for k,v in z.items() if isinstance(v,np.ndarray)})
 put('ALL_ANALYZED_RESULTS.json',dict(rows=out,analysis_unix=time.time(),physics_starts=0,unit_contract=dict(TV_v='rad/s',speed_variation='rad/s',TV_a='rad/s^2',jerk='rad/s^3',force='N',J_F='N s')))
 complete=[r for r in out if r['status']=='COMPLETE']
 for base in ['B','E']:
  selected=[r for r in complete if r['candidate']['base']==base and r['candidate'].get('changes')]
  if not selected:continue
  fig,axs=plt.subplots(4,2,figsize=(17,14),layout='constrained')
  for r in selected:
   z=zs[r['id']];b=zs[r['matched_baseline']];name=r['candidate']['id'];color=None
   line=axs[0,0].plot(z['tf'],z['f'],label=name)[0];color=line.get_color()
   if len(z['tf'])!=len(b['tf']):continue
   axs[1,0].plot(z['tf'],z['f']-b['f'],color=color);axs[2,0].plot(z['tf'],z['cf']-b['cf'],color=color)
   axs[3,0].scatter(r['full_TV_v_change_percent'],r['full_J_F_delta'],c=color,marker='o' if r['motion_pass'] else 'x');axs[3,0].annotate(name,(r['full_TV_v_change_percent'],r['full_J_F_delta']),fontsize=7)
   for c,loc in zip(r['candidate']['changes'],r['local']):
    lo,hi=c['local_window_task_s'];ix=(z['t']>=lo)&(z['t']<=hi);x=z['t'][ix]-lo
    axs[0,1].plot(x,np.degrees(z['v'][ix,0]),color=color,ls='-' if c['phase']=='OUTBOUND' else '--')
    axs[1,1].plot(x,np.degrees(z['v'][ix,1]),color=color,ls='-' if c['phase']=='OUTBOUND' else '--')
    axs[2,1].plot(x,np.linalg.norm(z['j'][ix],axis=1),color=color,ls='-' if c['phase']=='OUTBOUND' else '--')
    axs[3,1].scatter(100*(loc['candidate']['TV_v']/loc['baseline']['TV_v']-1),loc['candidate']['J_F']-loc['baseline']['J_F'],c=color,marker='o' if r['motion_pass'] else 'x')
  labels=[['Instantaneous force [N]','Support hip actual v [deg/s]'],['F − matched base [N]','Support knee actual v [deg/s]'],['Cumulative J_F − matched base [N s]','Support raw jerk norm [rad/s³]'],['Full ΔJ_F [N s]','Support ΔJ_F [N s]']]
  for i in range(4):
   for j in range(2):axs[i,j].set_ylabel(labels[i][j]);axs[i,j].grid(alpha=.2)
  axs[0,0].legend(fontsize=8,ncol=2);axs[2,0].set_xlabel('Task elapsed [s]');axs[2,1].set_xlabel('Elapsed within each respective support [s], not phase-aligned force');axs[3,0].set_xlabel('Full actual TV_v change [%]');axs[3,1].set_xlabel('Support actual TV_v change [%]')
  fig.suptitle(('B' if base=='B' else '18D')+' + targeted smoothing | all complete outcomes; x = motion FAIL')
  fig.savefig(P/'figures'/(base+'_intervention_comparison.png'),dpi=150);plt.close(fig)
 print(json.dumps([dict(id=r['id'],J_F=r.get('J_F'),motion=r.get('motion_pass'),delta=r.get('full_J_F_delta'),TV_change=r.get('full_TV_v_change_percent'),jerk_change=r.get('full_jerk_change_percent'),status=r['status']) for r in out],indent=2))
if __name__=='__main__':analyze()
