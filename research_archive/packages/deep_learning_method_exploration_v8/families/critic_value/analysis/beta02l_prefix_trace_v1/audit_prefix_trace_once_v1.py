"""独立新批准prefix trace审计：数组一次读取，0raw重扫/模型/物理。"""
from pathlib import Path
import hashlib
import json
import os
import resource
import signal
import sys
import time
import xml.etree.ElementTree as ET


def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while True:
   x=f.read(1024**2)
   if not x:break
   h.update(x)
 return h.hexdigest()
def load(p):return json.loads(p.read_text())
def save(p,d):
 with p.open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def usage():
 r=resource.getrusage(resource.RUSAGE_SELF)
 return {'unix':time.time(),'PID':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'CPU_user_s':r.ru_utime,'CPU_system_s':r.ru_stime,'RSS_peak_KiB':r.ru_maxrss,'affinity':sorted(os.sched_getaffinity(0)),'python':sys.executable,'binary_sha256':sha(Path(sys.executable).resolve())}


def main():
 P=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent;out=D/'run_once_v1'
 assert P.name=='deep_learning_method_exploration_v8' and not out.exists()
 os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(60,61))
 initial=usage();out.mkdir();save(out/'START.json',initial)
 def timeout(*_):raise TimeoutError('INDEPENDENT_PREFIX_TRACE_ORIGINAL_60S_STOP')
 signal.signal(signal.SIGTERM,timeout);signal.signal(signal.SIGALRM,timeout);signal.signal(signal.SIGXCPU,timeout);signal.setitimer(signal.ITIMER_REAL,59.5)
 ledger={'np_load_entry':0,'np_load_completed':0,'array_reads':{},'prefix_gate_reduction_entry':0,'prefix_gate_reduction_completed':0}
 result={'status':'STARTED','extra_model_init_forward_fit_physics':0,'large_raw_reread':0}
 try:
  import numpy as np
  assert np.__version__=='2.2.6' and sys.dont_write_bytecode
  parentreview=P/'families/critic_value/analysis/beta02l_parent_prefix_v1/PARENT_PREFIX_REVIEW_V1.json';prior=load(parentreview)
  trace=P/'runtime/source/results/V8BETA02L_B/trace.npz';Bdata=load(P/'runtime/output/V8BETA02L_B_DATA.json');summary=load(P/'runtime/source/results/V8BETA02L_B/summary.json');job=load(P/'jobs/V8BETA02L/SOURCE_MANIFEST.json')
  stem='runtime/source/stages/stage5_personalized_motion_learning/'
  contract_path=P/(stem+'docs/high_rom_v1/PHASE_B_MATRIX.json');sc=load(contract_path)['scoring']
  source_paths=[stem+'docs/high_rom_v1/PHASE_B_MATRIX.json',stem+'scripts/high_rom_v1/summarize_phase_b.py',stem+'src/traction_mpc_stage5/cr12_robot.py',stem+'src/traction_mpc_stage5/cr12_plant.py',stem+'models/cr12_v0.xml',stem+'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py']
  bindings={r:{'actual_sha256':sha(P/r),'original_job_sha256':job['files'].get(r)} for r in source_paths};assert all(v['actual_sha256']==v['original_job_sha256'] for v in bindings.values())
  motors={n.attrib['name']:n for n in ET.parse(P/(stem+'models/cr12_v0.xml')).getroot().find('actuator')}
  limits=[]
  for i in range(1,7):
   low,high=map(float,motors['joint'+str(i)+'_torque'].attrib['ctrlrange'].split());assert low==-high and high>0;limits.append(high)
  actual_trace_sha=sha(trace);assert actual_trace_sha==Bdata['metric']['trace_sha256']
  fields=['time_s','stage','physics_steps','evaluation_only_human_state_rad_rad_s','cr12_dq_rad_s','cr12_actuator_command_nm','actual_human_acceleration_rad_s2','actual_human_acceleration_valid','session_shank_clearance_m','dev_d_measured_sleeve_gap_m']
  ledger['np_load_entry']+=1
  with np.load(trace,allow_pickle=False) as z:
   headers=list(z.files);arrays={}
   for name in fields:
    if name in headers:
     ledger['array_reads'][name]=ledger['array_reads'].get(name,0)+1
     arrays[name]=z[name]
  ledger['np_load_completed']+=1
  assert all(v==1 for v in ledger['array_reads'].values())
  t=arrays['time_s'];stage=arrays['stage'];steps=arrays['physics_steps'];cutoff=prior['parent_accounting']['fork_physical_s']
  assert t.ndim==stage.ndim==steps.ndim==1 and len(t)==len(stage)==len(steps)
  mask=np.isin(stage,['ACTIVE_RECOVERY','COMMISSIONING']) & (t<=cutoff+1e-9)
  indices=np.flatnonzero(mask);assert len(indices)>0 and np.isfinite(t[mask]).all()
  last=int(indices[-1]);last_receipt=prior['receipts']['parent_last'];boundary=np.flatnonzero((np.abs(t-cutoff)<=1e-9)&(stage=='TASK'))
  binding={'prefix_trace_rows':len(indices),'stage_counts':{s:int(np.count_nonzero(mask&(stage==s))) for s in ['ACTIVE_RECOVERY','COMMISSIONING']},
   'first_time_s':float(t[indices[0]]),'last_time_s':float(t[last]),'first_physics_steps':int(steps[indices[0]]),'last_trace_physics_steps':int(steps[last]),
   'fork_native_and_receipt_steps':40200,'last_receipt_start_s':last_receipt['start_physics_s'],'last_receipt_end_s':last_receipt['end_physics_s'],'last_receipt_native_steps':last_receipt['native_steps'],
   'prefix_rows_equal_parent_receipt_count':len(indices)==prior['receipts']['parent_count'],
   'last_trace_aligns_last_receipt_start':abs(float(t[last])-last_receipt['start_physics_s'])<=1e-9,
   'last_trace_counter_plus_last_receipt_steps_equals40200':int(steps[last])+last_receipt['native_steps']==40200,
   'last_receipt_end_equals_fork':abs(last_receipt['end_physics_s']-cutoff)<=1e-9,
   'TASK_cutoff_boundary_metadata_only':[{'row':int(i),'time_s':float(t[i]),'physics_steps':int(steps[i])} for i in boundary],
   'TASK_values_not_reduced':True,'parent_TASK_native_steps':0,'prefix_native_step_source':'原receipt合计40200与raw native40200，额外trace只fast观测'}
  gates={};N=len(indices)
  def gate(name,field,transform,threshold,kind='max',valid_field=None):
   ledger['prefix_gate_reduction_entry']+=1
   if field not in arrays:
    gates[name]={'value':None,'status':'UNKNOWN_FIELD_ABSENT'};ledger['prefix_gate_reduction_completed']+=1;return
   assert arrays[field].shape[0]==len(t)
   selected=arrays[field][mask]
   valid=np.ones(N,dtype=bool) if valid_field is None else arrays[valid_field][mask].astype(bool)
   vals=transform(selected[valid]);finite=np.isfinite(vals)
   data={'source_field':field,'prefix_rows':N,'valid_rows':int(valid.sum()),'invalid_flag_rows':int((~valid).sum()),'finite_scalar_count':int(finite.sum()),'nonfinite_scalar_count':int((~finite).sum()),'threshold':threshold,'value':None,'status':'UNKNOWN_INSUFFICIENT_OBSERVATIONS'}
   if vals.size and finite.all():
    aggregate=np.max(np.abs(vals),axis=0) if kind=='max' else np.min(vals,axis=0)
    ok=np.all(aggregate<=np.asarray(threshold)) if kind=='max' else np.all(aggregate>=np.asarray(threshold))
    data.update(value=bool(ok),status='PASS_PREFIX_OBSERVED_ORIGINAL_THRESHOLD' if ok else 'FAIL_PREFIX_OBSERVED_ORIGINAL_THRESHOLD',observed_aggregate=np.asarray(aggregate).tolist())
   elif vals.size and name=='measured_sleeve_clearance' and finite.any():
    # 原scorer仅对有限sleeve观测取min；同时不把缺失区间伪装完整覆盖。
    minimum=float(np.min(vals[finite]));data.update(original_finite_only_formula_observed_min=minimum,original_finite_only_formula_pass=minimum>=threshold,full_prefix_coverage='UNKNOWN_NONFINITE_PREFIX_SAMPLES')
   gates[name]=data;ledger['prefix_gate_reduction_completed']+=1
  gate('torque','cr12_actuator_command_nm',lambda a:a/np.asarray(limits),sc['robot_torque_fraction_max'])
  gate('human_speed','evaluation_only_human_state_rad_rad_s',lambda a:np.degrees(a[:,2:]),sc['human_velocity_limit_deg_s'])
  gate('human_acceleration','actual_human_acceleration_rad_s2',lambda a:np.degrees(a),sc['human_acceleration_limit_deg_s2'],valid_field='actual_human_acceleration_valid')
  gate('robot_speed','cr12_dq_rad_s',lambda a:np.degrees(a),sc['robot_velocity_limit_deg_s'])
  gate('session_clearance','session_shank_clearance_m',lambda a:a,sc['clearance_m_min'],kind='min')
  gate('measured_sleeve_clearance','dev_d_measured_sleeve_gap_m',lambda a:a,sc['clearance_m_min'],kind='min')
  result.update(status='COMPLETED_ADDITIONAL_PREFIX_OBSERVATION_AUDIT_NOT_PARENT_QUALIFICATION',parent_review_sha256=sha(parentreview),
   trace_path=str(trace.relative_to(P)),trace_sha256=actual_trace_sha,original_B_data_trace_SHA_equal=True,source_bindings=bindings,
   shape_headers_only_fields=headers,array_shapes={k:list(v.shape) for k,v in arrays.items()},binding=binding,remaining6=gates,
   torque_limits_nm_from_original_XML=limits,
   finite_original_threshold_checks_only=True,
   original_parent_scorer_status='PARTIAL_NOT_RANKED_UNCHANGED',full_parent_task_pass=False,
   unknown_gates=[k for k,v in gates.items() if v['value'] is None],observed_failed_gates=[k for k,v in gates.items() if v['value'] is False],
   native_between_fast_samples_guarantee=False,all11_hard_false_for_root_cancellation='ROOT_MUST_REVIEW_SCOPE_AND_ANY_UNKNOWNS',
   ledger=ledger,numpy_identity={'version':np.__version__,'file':np.__file__,'module_sha256':sha(Path(np.__file__))},
   no_MuJoCo_or_policy_import=not any(x in sys.modules for x in ['mujoco','torch','beta_policy']))
  save(out/'RESULT.json',result)
 except BaseException as e:
  result.update(status='FAILED_PRESERVED_NO_RERUN',error_type=type(e).__name__,error=str(e),ledger=ledger);save(out/'FAILED_PAID_PREFIX.json',result);raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0.);save(out/'RESOURCE.json',{'START':initial,'END':usage(),'source_sha256':sha(Path(__file__)),'AS_bytes':1024**3,'single_CPU':True,'timeout_s':60,'automatic_retry':False,'np_array_reads':ledger['array_reads'],'model_init_forward_fit_physics':0})


if __name__=='__main__':main()
