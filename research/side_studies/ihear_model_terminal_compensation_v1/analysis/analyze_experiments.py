from pathlib import Path
import os,sys,json,ast,time,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;A=P.parent/'ihear_autonomous_multitrack_v1'
sys.dont_write_bytecode=True;sys.path[:0]=[str(P/'code'),str(P/'control')]
import study_common as sc
from stream_runtime_evidence import array_items
import numpy as np
import matplotlib.pyplot as plt
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(sc.clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
src=(A/'analysis/historical_audit.py').read_text();tree=ast.parse(src)
for name in ['load','terminal','variations']:exec(ast.get_source_segment(src,next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name)))
groups=sys.argv[1:] or ['Dev'];rows=[];zs={};execution=[]
for group in groups:
 result=P/(group+'_RESULTS.json')
 if not result.exists():continue
 rs=read(result)['rows'];base=load(P,group+'_B');er=load(P,group+'_ER');bJ=base['metric']['J_F_N_s'];eJ=er['metric']['J_F_N_s'];eos=terminal(er)[1]['return_overshoot_below_goal_deg']
 for row in rs:
  ident=row['id'];z=load(P,ident);zs[ident]=z;m=z['metric'];ter=terminal(z);run=P/'source/results'/ident
  stats={};controller=row['candidate'].get('controller');verified=True
  if controller:
   intents=read(P/'output'/(ident+'_CONTROL_INTENT.json'))['rows'];rr=list(array_items(run/'runtime_artifacts.json.gz','command_receipts'));ctrl=[r for r in rr if r.get('applied') and r.get('native_steps',0)>0 and 'terminal_control_contract' in r];record_by_t={round(r['sample_s'],9):r for r in intents};errors=[];active=0;executable=[]
   for r in ctrl:
    meta=r['terminal_control_contract'];ir=record_by_t.get(round(meta['sample_s'],9));active+=int(np.any(np.array(meta['delta_rad_s2'])!=0))
    if ir is None or not np.array_equal(meta['delta_rad_s2'],ir['delta_rad_s2']) or meta['candidate_hash']!=row['candidate']['candidate_hash']:errors.append(r['receipt_index'])
    if ir is not None:executable.append(ir['original_executable_filter_metadata'])
   delta=np.array([r['delta_rad_s2'] for r in intents]);corr=np.array([r.get('generalized_correction_nm',[0,0]) for r in intents]);ts=np.array([r['sample_s'] for r in intents]);stale=[r for r in intents if r['stale']]
   rates=np.max(abs(np.diff(delta,axis=0)/np.diff(ts)[:,None]),axis=0)
   verified=bool(ctrl and active and len(ctrl)==len(intents) and not errors and not stale and np.max(abs(delta))<=.2+1e-9 and np.max(rates)<=1.+1e-8 and all(r['truth_consumed']==False for r in intents) and all(r.get('status')=='SAFE_UNCHANGED' for r in executable))
   stats=dict(status='PASS' if verified else 'FAIL',intent_count=len(intents),positive_native_receipt_count=len(ctrl),active_positive_receipt_count=active,matched_record_errors=errors,stale_count=len(stale),max_delta_rad_s2=np.max(abs(delta),axis=0),max_rate_rad_s3=np.max(abs(np.diff(delta,axis=0)/np.diff(ts)[:,None]),axis=0),generalized_correction_peak_abs_nm=np.max(abs(corr),axis=0),saturation_count=sum(r['saturated'] for r in intents),rate_limit_count=sum(r['rate_limited'] for r in intents),filter_status_counts={str(s):sum(str(r.get('status'))==str(s) for r in executable) for s in set(str(r.get('status')) for r in executable)},candidate_hash=row['candidate']['candidate_hash'])
  traces=np.load(run/'trace.npz');task=traces['stage']=='TASK';tf=traces['time_s'][task]-traces['time_s'][task][0];command=traces['cr12_actuator_command_nm'][task];win=(tf>=15.3)&(tf<=18.)
  highfreq=[]
  for joint in range(2):
   vv=z['v'][:,joint];f=np.fft.rfftfreq(len(vv),.00025);power=abs(np.fft.rfft(vv-vv.mean()))**2;highfreq.append(float(np.sum(power[f>=20])/np.sum(power)))
  out={**row,'terminal':ter,'excursion_deg':m['dose']['excursion_deg'],'excursion_delta_B_deg':np.array(m['dose']['excursion_deg'])-base['metric']['dose']['excursion_deg'],'overshoot_delta_ER_deg':ter[1]['return_overshoot_below_goal_deg']-eos,'J_F_delta_ER_N_s':m['J_F_N_s']-eJ,'force_saving_retention_fraction':(bJ-m['J_F_N_s'])/(bJ-eJ),'force_peak_N':m['force_peak_N'],'force_RMS_N':np.sqrt(np.mean(z['f']**2)),'moment_integral_Nm_s':m['moment_integral_Nm_s'],'moment_peak_Nm':m['moment_peak_Nm'],'tracking_RMS_deg':m['tracking_RMS_deg'],'raw_full_motion':m['motion']['raw']['full'],'variations':variations(z),'clearance':m['clearance'],'robot_torque_peak_abs_nm':np.max(abs(command),axis=0),'terminal_robot_torque_TV_nm':np.sum(abs(np.diff(command[win],axis=0)),axis=0),'velocity_spectral_energy_fraction_ge20Hz':highfreq,'controller_execution':stats,'new_control_contract_verified':verified}
  out['fully_qualified']=bool(row['all_original_qualifications'] and verified)
  out['selection_eligible']=bool(out['fully_qualified'] and out['overshoot_delta_ER_deg']<=-.05+1e-10 and out['force_saving_retention_fraction']>=.8 and row['motion']['gain_percent']>=1.)
  starts=[json.loads(line) for line in (P/'ATTEMPTS.jsonl').read_text().splitlines() if json.loads(line).get('event')=='START' and json.loads(line).get('id')==ident]
  assert len(starts)==1
  out['actual_execution_manifest_sha']=starts[0]['code_manifest_sha256']
  rows.append(out);execution.append(dict(id=ident,controller=stats,source_manifest_sha=starts[0]['code_manifest_sha256']))
  if row['candidate'].get('timing'):
   # Timing contrast is physically identical before its new suffix is consumed.
   ertr=np.load(P/'source/results'/(group+'_ER')/'trace.npz');diff=np.flatnonzero(np.any(traces['reference_q_rad']!=ertr['reference_q_rad'],axis=1));first=float(traces['time_s'][diff[0]]) if len(diff) else None
   kneemax=float(np.max(abs(traces['reference_q_rad'][:,1]-ertr['reference_q_rad'][:,1])));native_er=np.load(P/'motion_series'/(group+'_ER.npz'));nn=np.load(P/'motion_series'/(ident+'.npz'));hist=nn['time_s']<first-1e-9 if first is not None else np.ones(len(nn['time_s']),bool)
   pre_equal=np.array_equal(nn['true_q_rad'][hist],native_er['true_q_rad'][hist]) and np.array_equal(nn['true_dq_rad_s'][hist],native_er['true_dq_rad_s'][hist])
   proof=dict(id=ident,first_reference_difference_physics_s=first,knee_reference_difference_max_rad=kneemax,all_human_q_dq_before_difference_exact=pre_equal,terminal_knee_actual_difference_max_deg=float(np.max(abs(z['q'][z['t']>=16.94,1]-er['q'][er['t']>=16.94,1]))),status='PASS' if pre_equal and kneemax<1e-10 else 'FAIL')
   put('audit/'+ident+'_HIP_ONLY_CAUSAL_PROOF.json',proof);assert proof['status']=='PASS'
closed=all((P/(g+'_OWNER.json')).exists() and read(P/(g+'_OWNER.json'))['joined'] for g in groups)
put('EXPERIMENT_RESULTS.json',dict(status=('COMPLETE' if all((P/(g+'_DONE.json')).exists() for g in groups) else 'CLOSED_WITH_PRESERVED_FAILED_ATTEMPTS') if closed else 'IN_PROGRESS',groups=groups,evidence='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',rows=rows,partial_ranked=False))
put('audit/CONTROL_EXECUTION_VERIFICATION.json',execution)
if 'Dev' in groups:
 rr=[r for r in rows if r['id'].startswith('Dev_')];labs=[r['candidate']['id'] for r in rr];fig,axs=plt.subplots(1,3,figsize=(16,5),layout='constrained')
 for r in rr:
  x=r['J_F_N_s'];color='#0072b2' if r['fully_qualified'] else '#d55e00'
  for ax,key in zip(axs,['moment_integral_Nm_s','terminal','excursion_delta_B_deg']):
   y=r[key][1]['return_overshoot_below_goal_deg'] if key=='terminal' else r[key][1] if key=='excursion_delta_B_deg' else r[key];ax.scatter(x,y,c=color);ax.annotate(r['candidate']['id'],(x,y),fontsize=8,xytext=(4,4),textcoords='offset points')
 for ax,l in zip(axs,['Moment integral (Nm s)','Knee overshoot (deg)','Knee excursion minus B (deg)']):ax.set_ylabel(l);ax.set_xlabel('Full J_F (N s)');ax.grid(alpha=.2)
 axs[2].axhline(.5,c='black',ls=':');fig.suptitle('Complete physical comparisons; orange = not fully qualified');fig.savefig(P/'figures/05_force_motion_moment.png',dpi=150);plt.close(fig)
 fig,axs=plt.subplots(4,1,figsize=(12,13),sharex=True,layout='constrained')
 for r in rr:
  if r['candidate']['id'] in ['T','D']:continue
  z=zs[r['id']];wn=(z['t']>=15.8)&(z['t']<=18.3);wf=(z['tf']>=15.8)&(z['tf']<=18.3);lab=r['candidate']['id'];axs[0].plot(z['t'][wn],z['q'][wn,1],label=lab);axs[1].plot(z['t'][wn],z['v'][wn,0],label=lab);axs[2].plot(z['tf'][wf],z['f'][wf],label=lab);axs[3].plot(z['tf'][wf],z['moment'][wf],label=lab)
 for ax,l in zip(axs,['Knee q (deg)','Hip velocity (deg/s)','Cuff force (N)','Cuff moment (Nm)']):ax.set_ylabel(l);ax.grid(alpha=.2);ax.set_xlim(15.8,18.3)
 axs[0].set_ylim(7.8,12.5);axs[0].axhline(9.5,c='black',ls=':',lw=.7);axs[0].legend(ncol=4);axs[-1].set_xlabel('Task time (s)');fig.savefig(P/'figures/06_interventions_terminal.png',dpi=150);plt.close(fig)
for f in [P/'EXPERIMENT_RESULTS.json',P/'audit/CONTROL_EXECUTION_VERIFICATION.json',*list((P/'figures').glob('*.png'))]:
 dst=R/f.relative_to(P);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dst)
print(json.dumps(sc.clean([dict(id=r['id'],J_F=r['J_F_N_s'],overshoot=r['terminal'][1]['return_overshoot_below_goal_deg'],delta_B=r['excursion_delta_B_deg'][1],full=r['fully_qualified'],eligible=r['selection_eligible'],control=r['controller_execution']) for r in rows])),flush=True)
