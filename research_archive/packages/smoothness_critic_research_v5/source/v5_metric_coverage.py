"""Final candidate raw/metric cadence, completeness and task-duration audit."""
from pathlib import Path
import os,sys,json,hashlib,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');out=[];errors=[];durations=[]
def get(n):return json.loads((P/n).read_text())
def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as s:
  for b in iter(lambda:s.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
for f in sorted((P/'attempts').glob('*_RESULT.json')):
 r=json.loads(f.read_text());ident=r['id'];group=ident.split('_')[0];bad=[]
 if not r['complete']:
  out.append(dict(id=ident,status='PARTIAL_RETAINED_NOT_RANKED',original_qualified=r['qualified']));continue
 e=get('analysis/extended/'+ident+'.json');cfg=get('experiments/'+group+'.json');root=P/'runtime/source/results'/ident
 if e['qualified']!=r['qualified']:bad.append('ORIGINAL_QUALIFICATION_CHANGED')
 if sha(root/'runtime_artifacts.json.gz')!=e['source_raw_sha256']:bad.append('EXTENDED_RAW_IDENTITY')
 with np.load(P/'runtime/motion_series'/(ident+'.npz')) as z:
  nt=z['time_s'];q=z['true_q_rad'];v=z['true_dq_rad_s'];a=z['acceleration_rad_s2'];j=z['jerk_rad_s3'];cadence=np.diff(nt);n=len(nt)
  if min(cadence)<=0 or np.max(abs(cadence-.00025))>1e-10:bad.append('NATIVE_CADENCE')
  if not all(np.isfinite(x).all() for x in [q,v,a,j]):bad.append('NATIVE_SIGNAL_NONFINITE')
  for key,x in [('velocity_deg_s',v),('acceleration_deg_s2',a),('jerk_deg_s3',j)]:
   x=np.degrees(x);rms=np.sqrt(np.mean(x*x,axis=0));peak=np.max(abs(x),axis=0);saved=e['native_motion'][key]
   if np.max(abs(rms-saved['rms']))>1e-7 or np.max(abs(peak-saved['peak_abs']))>1e-7:bad.append('UNFILTERED_NATIVE_STAT_BINDING:'+key)
 with np.load(root/'trace.npz') as z:
  k=z['stage']=='TASK';t=z['time_s'][k];duration=float(t[-1]-t[0]);wrench_finite=all(np.isfinite(z[field][k]).all() for field in ['physical_cuff_force_world_n','physical_cuff_moment_world_nm','cr12_actuator_command_nm'])
  if not wrench_finite:bad.append('ORIGINAL_PHYSICAL_SIGNAL_NONFINITE')
 b=get('analysis/extended/'+group+'_B.json');duration_difference=duration-b['duration_s'];durations.append(duration)
 if abs(duration_difference)>1e-8:bad.append('COMPLETE_DURATION_DIFFERS_FROM_MATCHED_ORIGINAL_B')
 if abs(duration-e['duration_s'])>1e-9:bad.append('DURATION_METRIC_IDENTITY')
 if abs(sum(p['J_F_N_s'] for p in r['phase_cost'].values())-r['JF'])>1e-7:bad.append('JF_PHASE_INTEGRAL_CLOSURE')
 if abs(sum(p['moment_integral_Nm_s'] for p in r['phase_cost'].values())-r['JM'])>1e-7:bad.append('JM_PHASE_INTEGRAL_CLOSURE')
 if not (P/'analysis/execution'/(ident+'.json')).is_file():bad.append('ACTUAL_REFERENCE_EXECUTION_ANALYSIS_MISSING')
 expected_native='v5_native_wrench.install()' in (P/'source'/cfg['worker']).read_text();native_file=P/'analysis/native_wrench'/(ident+'.json')
 if expected_native and not native_file.exists():bad.append('HIGHEST_AVAILABLE_WRENCH_METRIC_MISSING')
 if native_file.exists():
  nw=json.loads(native_file.read_text());ov=nw['original_5ms_overlap']
  if ov['force_max_abs_error_N']>1e-8 or ov['moment_max_abs_error_Nm']>1e-8:bad.append('NATIVE_ORIGINAL_5MS_WRENCH_IDENTITY')
  with np.load(P/'runtime/motion_series'/(ident+'_NATIVE_WRENCH.npz')) as z:
   if len(z['time_s'])!=n or np.max(abs(z['time_s']-nt))>1e-10:bad.append('NATIVE_WRENCH_MOTION_TIME_IDENTITY')
   if not np.isfinite(z['force_world_n']).all() or not np.isfinite(z['moment_world_nm']).all():bad.append('NATIVE_WRENCH_NONFINITE')
 out.append(dict(id=ident,status='PASS' if not bad else 'FAIL',original_qualified=r['qualified'],native_samples=n,native_dt_s=float(np.median(cadence)),duration_s=duration,matched_B_duration_difference_s=duration_difference,original_JF=r['JF'],original_JM=r['JM'],available_wrench_cadence_s=.00025 if native_file.exists() else .005,errors=bad));errors.extend([ident+':'+b for b in bad])
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS' if not errors else 'FAIL',rows=out,errors=errors,complete_candidate_results=sum(r['status'] in ['PASS','FAIL'] for r in out),native_wrench_candidates=sum(r.get('available_wrench_cadence_s')==.00025 for r in out),original_5ms_only_candidates=sum(r.get('available_wrench_cadence_s')==.005 for r in out),minimum_full_task_duration_s=min(durations),maximum_full_task_duration_s=max(durations),scope='Full candidate raw and metrics only; parents are separately checked by original scorer and full receipt/native audit. Unfiltered native saved arrays bind to reported RMS/peaks; independent original scorer service separately reconstructs derivatives from raw. All actual force/moment/applied torque finite; one missing terminal requested-component record remains explicitly disclosed.',new_physical_START=0)
(P/'audit/RAW_METRIC_COVERAGE_AND_DURATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('METRIC_COVERAGE',result['status'],'candidates',len(out),'errors',errors[:10]);assert not errors,errors
