"""Exact frozen-path replay, observational handoff hooks only."""
import os,sys,json,time,resource,hashlib
from pathlib import Path
from dataclasses import replace
W=Path('<SIDE_STUDIES_ROOT>/commissioning-to-recovery-geometry-compatibility-v1')
sys.path.insert(0,str(W));sys.dont_write_bytecode=True
import human_qualification_R2 as h
rt=h.rt;np=h.np
from lab_resource_guard_R2 import verify_release,ResourceStop,sample
label=os.environ['GEOM_RUN_LABEL'];arm=os.environ['LAB_STUDY_ARM'];phase=os.environ.get('GEOM_PHASE','baseline')
root=W/phase/label;h.D=root;h.OUT=root/'runs'
run=h.OUT/('C5__'+arm);os.environ['LAB_RUN_DIR']=str(run)
c=json.loads((W/'CONTRACT_R2.json').read_text());condition=c['conditions'][5]
if label=='C5_existing_oracle':
 from traction_mpc_stage5.fresh_qualification_v1.scenario import hidden_plant
 human,fixture,spec,probes=hidden_plant(condition['case'])
 original_geometry=rt.nominal_control_geometry()
 oracle_geometry=replace(original_geometry,origin_world_m=fixture.world_from_human.translation.copy(),hip_plane_m=np.zeros(2),thigh_length_m=human.thigh_length_m,knee_to_cuff_in_cuff_m=np.array([human.sleeve_center_m,0.]))
 rt.nominal_control_geometry=lambda:oracle_geometry
original_init=rt._initialize_loaded_runtime
def init(*args,**kwargs):
 r=original_init(*args,**kwargs)
 h.save(run/'INITIALIZATION_ALIGNMENT.json',dict(model_geometry=vars(r['model'].geometry),model_beta=r['model'].beta,initial_support_state=r['initial_support_state'],offline_support_setup=r.get('offline_support_setup'),startup_alignment_record=r.get('startup_alignment_record'),plant_qpos_evaluation_only=r['plant'].data.qpos.copy(),plant_qvel_evaluation_only=r['plant'].data.qvel.copy(),diagnostic_plant_state_never_fed_to_controller=True))
 return r
rt._initialize_loaded_runtime=init
original_recovery=rt._run_dev_a_active_recovery
def recovery(runtime,**kwargs):
 b=kwargs['updater'].snapshot();trace=kwargs['trace'];pose=kwargs['old_robot_cuff_pose'];cl=kwargs['clearance'];env=cl.envelope
 h.save(run/'HANDOFF_EXACT.json',dict(time_s=float(runtime['plant'].data.time),last_trace=trace[-1],old_model_geometry=vars(kwargs['old_model'].geometry),target_model_geometry=vars(b.human_model().geometry),target_beta=b.beta,target_residual=b.state_residual_weights_nm,old_emitted_pose=dict(translation=pose.translation,rotation=pose.rotation),envelope_record=cl.record(),envelope_geometry_same_object_as_target=(env.geometry is b.geometry),commissioning_reference_origin=runtime.get('commissioning_cuff_reference_origin'),initial_support_state=runtime['initial_support_state'],plant_qpos_evaluation_only=runtime['plant'].data.qpos.copy(),plant_qvel_evaluation_only=runtime['plant'].data.qvel.copy(),ownership=dict(runtime_model='commissioned target on entry; original routine defers activation until certified recovery',contract_same_model=runtime['contract'].human_model is runtime['model'],scheduler_geometry=vars(kwargs['scheduler'].human_model.geometry)),hidden_truth_only_diagnostic=True))
 result=original_recovery(runtime,**kwargs)
 h.save(run/'RECOVERY_EXACT.json',result)
 return result
rt._run_dev_a_active_recovery=recovery
if __name__=='__main__':
 assert not root.exists(),'never overwrite a run'
 prov=json.loads((W/'SOURCE_PROVENANCE.json').read_text())
 assert all(h.sha(h.R/p)==r['sha256'] for p,r in prov['source_files'].items())
 imports={k:v.__file__ for k,v in sys.modules.items() if k.startswith('traction_mpc') and getattr(v,'__file__',None)}
 assert all(p.startswith(str(h.R)) for p in imports.values())
 r=verify_release();root.mkdir(parents=True)
 h.save(root/'IMPORT_ENVIRONMENT.json',dict(imports=imports,python=sys.executable,threads={k:os.environ[k] for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']},oracle_diagnostic_only=label=='C5_existing_oracle'))
 h.save(root/'CONTRACT_R2.json',c);h.save(root/'STATE_R2.json',dict(status='REPLAY',active_seconds=0,primary_attempts=0))
 fd=os.open(W/'PHYSICS_OWNER.lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 state=json.loads((W/'STATE.json').read_text());state['dynamic_attempts']+=1;h.save(W/'STATE.json',state)
 h.resource_stop=ResourceStop(r);sys.argv=[__file__,'C5'];start=time.monotonic()
 try:
  h.main()
  q=json.loads((run/'qualification.json').read_text())
  if q['completion']=='EXCEPTION':raise RuntimeError(q['exception'])
  import postprocess_lab_run_R2 as post
  result=post.process(run);result.update(row_scope='exact_path_reproduction',oracle_diagnostic_only=label=='C5_existing_oracle');h.save(run/'PRIMARY_RESULT.json',result)
  sample();state=json.loads((W/'STATE.json').read_text());state['completed_runs'].append(label);state['status']='BASELINE_RUNNING';h.save(W/'STATE.json',state)
  print('RESULT',label,result['status'],result['physical_verdict'],result['scientific_verdict'],flush=True)
 finally:
  h.save(root/'RUN_RESOURCE.json',dict(wall_seconds=time.monotonic()-start,parent_peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,child_peak_RSS_KiB=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
  (W/'PHYSICS_OWNER.lock').unlink(missing_ok=True)
