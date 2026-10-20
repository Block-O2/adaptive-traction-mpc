"""Post-run exact force/moment phase integrals, resource summary and figures."""
from common import *
import csv
def integration(row):
 z=np.load(R/row['trace']);mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][mask],axis=1);p=z['task_phase'][mask];dt=np.diff(t);fc=f[:-1]*dt;mc=m[:-1]*dt
 return dict(name=row['name'],scope=row['scope'],valid=row['valid'],phase_durations=row.get('phase_durations'),J_F=float(fc.sum()),phase_J_F={ph:float(fc[p[:-1]==ph].sum()) for ph in ('OUTBOUND','HOLD','RETURN')},M_integral=float(mc.sum()),phase_M_integral={ph:float(mc[p[:-1]==ph].sum()) for ph in ('OUTBOUND','HOLD','RETURN')},phase_F_peak={ph:float(f[p==ph].max()) if np.any(p==ph) else None for ph in ('OUTBOUND','HOLD','RETURN')},phase_M_peak={ph:float(m[p==ph].max()) if np.any(p==ph) else None for ph in ('OUTBOUND','HOLD','RETURN')},integration='left endpoint 5ms physical trace intervals, phase of left endpoint; all waiting retained',trace_sha256=sha(R/row['trace']))
def run():
 result=read('RESULTS.json');base=read('FROZEN_STUDENT_BASELINE.json');comps=json.loads((W/'dagger_to_sac_expert_v1/output/SUMMARY.json').read_text())['COMPARATORS'];pause=read('RESOURCE_PAUSE_CLOSEOUT.json');latest=pause['latest_native_10000'][0];selected=[base['NATIVE'],base['MATCHED']]+[v['row'] for v in result['best'].values()]+[latest,pause['latest_matched_10000'][0]];rows=[integration(r) for r in selected]
 for c in comps:
  if c.get('trace'):
   assert sha(R/c['trace'])==c['trace_sha256'];rows.append(integration(c))
 delta={}
 if result['best'].get('NATIVE'):
  b=rows[0];best=next(r for r in rows if r['name']==result['best']['NATIVE']['row']['name']);delta=dict(J_F_delta=best['J_F']-b['J_F'],phase_J_F_delta={p:best['phase_J_F'][p]-b['phase_J_F'][p] for p in ('OUTBOUND','HOLD','RETURN')},phase_time_delta={p:best['phase_durations'][p]-b['phase_durations'][p] for p in ('OUTBOUND','HOLD','RETURN')},claim='phase force changes and duration changes are descriptive decomposition, not isolated pure coordination improvement')
 b=rows[0];last=next(r for r in rows if r['name']==latest['name']);candidate_delta=dict(J_F_delta=last['J_F']-b['J_F'],phase_J_F_delta={p:last['phase_J_F'][p]-b['phase_J_F'][p] for p in ('OUTBOUND','HOLD','RETURN')},phase_time_delta={p:last['phase_durations'][p]-b['phase_durations'][p] for p in ('OUTBOUND','HOLD','RETURN')},extra_best_confirmation_pending=True)
 save('PHASE_COST_DECOMPOSITION.json',dict(rows=rows,best_vs_student=delta,latest_candidate_vs_student=candidate_delta))
 resource_rows=[]
 for name in ('RESOURCES.jsonl','RESOURCE_EXTERNAL.jsonl'):
  if (L/name).exists():resource_rows += [json.loads(x) for x in (L/name).read_text().splitlines()]
 progress=[json.loads(x) for x in (L/'WORKFLOW.log').read_text().splitlines() if x.startswith('{') and 'steps_per_s' in x and 'ANCHORED_SAC_ONLINE' in x];pss=[r['processes']['owned'][0].get('Pss',0) for r in resource_rows];speed=[r['steps_per_s'] for r in progress];resource_summary=dict(checks=len(resource_rows),main_PSS_max_GiB=max(pss)/2**30,swap_peak_MiB=max(r['swap_bytes'] for r in resource_rows)/2**20,WSL_available_min_GiB=min(r['wsl']['MemAvailable'] for r in resource_rows)/2**30,host_commit_headroom_min_GiB=min(r['windows']['CommitLimit']-r['windows']['CommittedBytes'] for r in resource_rows)/2**30,GPU_total_device_memory_used_max_MiB=max(float(r['gpu'].split(',')[0]) for r in resource_rows),online_steps_per_s_median=None if not speed else float(np.median(speed)),online_steps_per_s_range=None if not speed else [min(speed),max(speed)],all_checks_safe=all(not r['reasons'] for r in resource_rows),wall_hours=(time.time()-read('STATE.json')['started_unix'])/3600)
 save('RESOURCE_SUMMARY.json',resource_summary)
 ex=read('EXPLORATION_CALIBRATION.json');a=actor();a.load_state_dict(torch.load(V/'qualified_actor.pt',map_location='cpu',weights_only=False)['state_dict']);obs=np.load(O/'IMITATION_ONLY.npz')['observations']
 with torch.no_grad():mean=a(torch.as_tensor(obs),True).numpy()
 sigma=62.5*(1-mean**2)*np.exp(ex['selected_log_std']);save('EXPLORATION_UNITS_CORRECTED.json',dict(selected_log_std=ex['selected_log_std'],conservative_target_sigma_bound_deg=62.5*np.exp(ex['selected_log_std']),per_joint_local_target_sigma_median_deg=np.median(sigma,axis=0),per_joint_local_target_sigma_peak_deg=sigma.max(axis=0),correction='original calibration local-sigma fields described the first -8 candidate; this file explicitly recomputes selected frozen configuration after independent-RNG recalibration',independent_success_count=ex.get('actual_independent_random_success'),original_duplicate_rng_repeats_excluded_from_independent_success=True))
 curves=[]
 for cp in result['checkpoints']:
  prefix=f"legacy_predict_revision/checkpoint/a{cp['attempt']}_p{cp['point']}_";native=next(r for r in result['evaluations'] if r['name']==prefix+'NATIVE_1');curves.append(dict(**cp,J_F_VALID_only=native['J_F'] if native['valid'] else None,OUTBOUND=native['phase_durations']['OUTBOUND'],HOLD=native['phase_durations']['HOLD'],RETURN=native['phase_durations']['RETURN'],termination=native['termination']))
 last_actor=actor();last_actor.load_state_dict(torch.load(Path(pause['latest_native_good_checkpoint'])/'actor.pt',map_location='cpu',weights_only=False));
 with torch.no_grad():drift=last_actor(torch.as_tensor(obs),True).numpy()-mean
 latest_drift=float(np.sqrt(np.mean(drift**2)));save('LATEST_CANDIDATE_DRIFT.json',dict(mean_drift_RMSE=latest_drift,mean_drift_peak=float(np.abs(drift).max()),checkpoint=pause['latest_native_good_checkpoint'],probe='all 13852 immutable DAgger observations, same-device deterministic pre-unscale means'))
 curves.append(dict(attempt=1,point=10000,total_online_steps=21283,native_valid=2,matched_valid=0,stochastic_valid=pause['latest_stochastic_10000'][0]['valid'],mean_drift_RMSE=latest_drift,mean_drift_peak=float(np.abs(drift).max()),checkpoint=pause['latest_native_good_checkpoint'],lambda_=10000.,std=-10.,J_F_VALID_only=latest['J_F'],OUTBOUND=latest['phase_durations']['OUTBOUND'],HOLD=latest['phase_durations']['HOLD'],RETURN=latest['phase_durations']['RETURN'],termination=latest['termination']))
 with (L/'LEARNING_CURVE.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(curves[0]));writer.writeheader();writer.writerows(curves)
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,axes=plt.subplots(3,1,figsize=(9,9),sharex=True);x=np.array([r['total_online_steps'] for r in curves]);jf=np.array([np.nan if r['J_F_VALID_only'] is None else r['J_F_VALID_only'] for r in curves]);axes[0].plot(x,jf,'o-',label='Anchored SAC, complete NATIVE VALID only')
 for c in comps:
  if c['scope']=='NATIVE' and c.get('valid'):axes[0].axhline(c['J_F'],ls='--',lw=.9,label=c['name'])
 axes[0].axhline(base['NATIVE']['J_F'],ls=':',color='black',label='frozen DAgger student');axes[0].set_ylabel('J_F (N s)');axes[0].legend(fontsize=7,loc='best')
 for i,r in enumerate(curves):
  if r['J_F_VALID_only'] is None:axes[0].annotate('INVALID',(x[i],base['NATIVE']['J_F']),xytext=(0,7),textcoords='offset points',ha='center',fontsize=7,color='red')
 for p in ('OUTBOUND','HOLD','RETURN'):axes[1].plot(x,[r[p] for r in curves],'o-',label=p)
 axes[1].set_ylabel('Actual phase duration (s)');axes[1].legend(fontsize=8);axes[2].plot(x,[r['mean_drift_RMSE'] for r in curves],'o-',label='mean action drift');axes[2].set_ylabel('Mean drift RMSE');axes[2].set_xlabel('Cumulative new collection steps, including calibration, failures and rescue')
 for ax in axes:ax.grid(alpha=.2)
 axes[0].annotate('10k: extra best replay pending', (x[-1],jf[-1]),xytext=(-180,-20),textcoords='offset points',fontsize=8);fig.suptitle('DAgger-Anchored SAC v2 — resource pause, one training seed');fig.text(.5,.01,'Deterministic repeats are reproducibility checks. INVALID partial costs are never ranked.',ha='center',fontsize=8);fig.tight_layout(rect=(0,.025,1,.96));fig.savefig(L/'LEARNING_CURVE.png',dpi=170);fig.savefig(L/'LEARNING_CURVE.pdf');plt.close(fig)
 print(json.dumps(clean(dict(resources=resource_summary,decomposition=delta))),flush=True)
if __name__=='__main__':run()
