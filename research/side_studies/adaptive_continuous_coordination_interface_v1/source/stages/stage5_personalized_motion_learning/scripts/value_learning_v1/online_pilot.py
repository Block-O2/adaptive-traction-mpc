"""Small continuous pilot with versioned inter-repetition cost learning.

At the first OUTBOUND decision, safe next-target candidates carry explicitly
declared smooth continuation paths. The accepted target commits that path;
future waypoints use the authoritative feedback/scheduling stack. This gives
honest Q(x,a|continuation) and temporally coherent exploration without claiming
the first waypoint alone causes a whole-pattern benefit.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,TimeoutError,Future
from pathlib import Path
import argparse,json,os,sys,time
from datetime import datetime
import numpy as np
from value_dataset import R,S,D,RAW,C,extract_run,save as dataset_save,sha
from value_models import fit_ridge,fit_mlp,save_model,ValidatedModelSlot,load_model
import run_research_rollout as runner
from traction_mpc_stage5.full3d_adaptive_integration_v1.runtime import advance_inter_rep_boundary
from zero_value_30rep_checkpoint import save_checkpoint,load_checkpoint
from evidence_io import archive_outputs,read_json

BANK=[{'parameters':[amp,.5],'horizon':'H3','return_reverse':False} for amp in (0.,-.03,.06,.12,.03,.09,.15)]
BANK += [{'parameters':[.06,peak],'horizon':'H3','return_reverse':False} for peak in (.3,.7)]
BANK += [{'parameters':[.03,.5],'horizon':'H4','return_reverse':True}]

def save(path,value):
 # Native boundary receipts contain arrays/scalars; use the runner's existing
 # logging conversion, without changing the checkpoint or controller state.
 return dataset_save(path,runner._jsonable(value))

def train_update(X,y,names,kind,path,metadata,validation=None):
 start=time.perf_counter()
 model=fit_ridge(X,y,alpha=metadata.get('ridge_regularization_alpha',10.),feature_names=names,metadata=metadata) if kind=='ridge' else fit_mlp(X,y,validation=validation,epochs=250,seed=20260930,metadata=metadata)
 model_sha=save_model(path,model)
 return {'path':str(path),'sha256':model_sha,'wall_s':time.perf_counter()-start,'training_rows':len(X),'metadata':metadata}

def run_mode(mode,condition,kind,prior_data,output_tag,latency_configuration,resume=False):
 directory=RAW/'pilot_sessions'/output_tag
 continuing=resume and directory.exists()
 if not continuing:directory.mkdir(parents=True,exist_ok=False)
 provenance={'schema':'value_learning_pilot_session_v1','condition':condition,'mode':mode,'value_model_kind':kind,
  'source_head':runner.subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip(),
  'proposal_bank':BANK,'latency_configuration':latency_configuration,'cross_condition_prior':mode=='PRIOR','prior_excludes_current_condition_and_test':True,
  'scope':'first next target commits recorded smooth continuation; full feedback and safety stay live; not arbitrary first-action credit',
  'max_attempted_repetitions':8,'update_wait_bound_s':2.,'convergence_thresholds_not_fixed_yet':True}
 if continuing:
  original=json.loads((directory/'session_provenance.json').read_text())
  for key in ('condition','mode','value_model_kind','proposal_bank'):
   if original[key]!=provenance[key]:raise ValueError('resume provenance changed: '+key)
  old_configuration=original['latency_configuration']
  # A separately frozen development computation revision may begin only at
  # this restored closed-episode boundary. Targets, model/hyperparameters,
  # candidate repertoire and original safety math must remain unchanged.
  added={'lazy_legacy_comparator_on_committed','proposal_bank_source_indices'}
  if {k:v for k,v in latency_configuration.items() if k not in added}!={k:v for k,v in old_configuration.items() if k not in added}:
   raise ValueError('resume changed scientific proposal/model configuration')
  if old_configuration!=latency_configuration:
   amendment=directory/'boundary_computation_amendment_v3.json'
   if not amendment.exists():save(amendment,{'original_provenance_sha256':sha(directory/'session_provenance.json'),'old_configuration':old_configuration,'revised_configuration':latency_configuration,'current_latency_gate_sha256':sha(D/'ONLINE_LATENCY_PROMOTION_GATE.json'),'source':'separately frozen and validated v3 duplicate-computation development revision','physics_targets_safety_math_unchanged':True,'effective_from_repetition':2,'earlier_rep1_preserved_under_original_computation_version':True})
  provenance=original
 else:save(directory/'session_provenance.json',provenance)
 provenance_sha=sha(directory/'session_provenance.json')
 context={};runner.SESSION_CONTEXT=context
 slot=ValidatedModelSlot();pending=None;updates=[];rows=[];learning_rows=[]
 names=json.loads((D/'VALUE_DATASET_SCHEMA.json').read_text())['feature_names']
 X_prior,y_prior=prior_data
 start_repetition=1
 if continuing:
  rows=json.loads((directory/'per_repetition.json').read_text())
  updates=json.loads((directory/'training_updates.json').read_text())
  learning_rows=[json.loads(line) for line in (directory/'online_rows.jsonl').read_text().splitlines() if line]
  if not rows or rows[-1]['status']!='VALID':raise ValueError('resume requires last valid continuous checkpoint')
  checkpoint=rows[-1]['end_checkpoint']
  context,checkpoint_rows=load_checkpoint(Path(checkpoint['absolute_path']),expected_sha256=checkpoint['sha256'],provenance_sha256=provenance_sha)
  if len(checkpoint_rows)!=len(rows):raise ValueError('checkpoint repetition count mismatch')
  runner.SESSION_CONTEXT=context;start_repetition=rows[-1]['repetition_index']+1
  active=rows[-1].get('model_path_used')
  if active:
   slot.active_path=active;slot.active_version=rows[-1]['model_version_used']
   if sha(Path(active))!=slot.active_version:raise ValueError('active resume model hash mismatch')
  prepared=[u for u in updates if u.get('after_repetition')==rows[-1]['repetition_index'] and u.get('path')]
  if prepared:
   result=prepared[-1]
   if sha(Path(result['path']))!=result['sha256']:raise ValueError('prepared resume model hash mismatch')
   pending=Future();pending.set_result(result)
  save(directory/f'resume_before_{start_repetition:02d}.json',{'source_checkpoint':checkpoint,'provenance_sha256':provenance_sha,'restored_repetitions':len(rows),'no_replayed_completed_repetition':True,'pending_model_promoted_only_at_next_original_safe_boundary':True})
 if mode=='PRIOR' and not continuing:
  model_path=directory/'models/prior_v0.npz';result=train_update(X_prior,y_prior,names,kind,model_path,{'mode':'PRIOR','excludes_condition':condition,'current_condition_online_rows':0,'ridge_regularization_alpha':latency_configuration.get('ridge_regularization_alpha',10.)})
  slot.propose(model_path,X_prior[:8]);slot.switch(at_safe_repetition_boundary=True);updates.append({**result,'stage':'offline_other_condition_prior_initialization'})
 pool=ThreadPoolExecutor(max_workers=1)
 try:
  for repetition in range(start_repetition,9):
   if time.time()>=datetime.fromisoformat(C['hard_deadline_utc']).timestamp():break
   boundary=None
   if context:
    boundary=advance_inter_rep_boundary(context,max_wait_s=2.)
    save(directory/f'boundary_before_{repetition:02d}.json',boundary)
   if pending and pending.done():
    try:
     result=pending.result();slot.propose(result['path'],np.asarray([x['features'] for x in learning_rows[-8:]]));slot.switch(at_safe_repetition_boundary=True)
     updates.append({**result,'stage':'repetition_boundary_update','promoted_before_repetition':repetition})
    except Exception as error:updates.append({'stage':'update_rejected_previous_model_retained','before_repetition':repetition,'error':str(error)})
    pending=None
   prior_native_state=None
   if context:
    plant=context['runtime']['plant'];prior_native_state={'qpos':plant.data.qpos.tolist(),'qvel':plant.data.qvel.tolist(),'time_s':float(plant.data.time),'human_model_sequence':context['updater'].sequence}
   proposal_indices=latency_configuration.get('proposal_indices',list(range(len(BANK))))
   proposals=[BANK[i] for i in proposal_indices]
   spec={'mode':'VALUE_PATTERN','proposal_descriptors':proposals,'descriptor':{'parameters':[0,.5],'horizon':'H3'},'matched_duration_factor':1.3,'model_path':slot.active_path,'model_version':slot.active_version}
   if latency_configuration.get('legacy_candidate_limit') is not None:spec['legacy_candidate_limit']=latency_configuration['legacy_candidate_limit']
   for key in ('lazy_legacy_comparator_on_committed','proposal_bank_source_indices'):
    if key in latency_configuration:spec[key]=latency_configuration[key]
   # Scratch starts with no value information. Two initial coherent legal
   # probes establish local data; subsequent decisions use updated value.
   if mode=='SCRATCH' and repetition<=2:spec['force_descriptor_index']=proposal_indices.index({1:2,2:3}[repetition])
   run_id=f'pilot_{output_tag}_rep_{repetition:02d}'
   out=RAW/'runs'/run_id
   record=runner.run(condition,'MATCHED',spec,run_id)
   processing_start=time.perf_counter()
   capture=runner.LAST_CAPTURE
   if record['status']=='VALID':
    fresh_rows=extract_run(out,record,'online_'+mode.lower());learning_rows+=fresh_rows
    with (directory/'online_rows.jsonl').open('a') as f:
     for row in fresh_rows:f.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
    summary=read_json(next(out.glob('rep_*'))/'summary.json')
    chosen=[x for x in summary['decisions'] if x.get('phase')=='OUTBOUND' and 'evaluations'in x][0]
    selected=next(x for x in chosen['evaluations'] if x['label']==chosen['executed_label'])
    rc=selected['execution_screen']['research_context'];latency=selected['execution_screen']['research_latency']
    first_row=fresh_rows[0];pred=selected['execution_screen'].get('predicted_remaining_cost_n_s')
    q_error=None if pred is None else abs(float(pred)-first_row['return_full_n_s'])
    row={'session_id':output_tag,'repetition_index':repetition,'condition_id':condition,'mode':mode,'run_id':run_id,'status':'VALID',
     'J_F_task_n_s':record['J_F_task_n_s'],'J_F_session_n_s':record['J_F_session_n_s']+(0 if boundary is None else boundary['cost']['J_F_n_s']),
     'boundary_before':boundary,'model_version_used':slot.active_version,'model_path_used':slot.active_path,'selected_continuation':rc['continuation_descriptor'],
     'selected_first_action_rad':selected['target_q_rad'],'first_decision_prediction_error_n_s':q_error,'first_decision_latency':latency,
     'force_peak_n':record['peak_force_n'],'minimum_clearance_m':record['minimum_clearance_m'],'duration_s':record['duration_s'],
     'start_native_state_evaluation_only':prior_native_state,'human_model_sequence_after':context['updater'].sequence,
     'online_training_rows_accumulated':len(learning_rows),'candidate_Q_at_first_decision':selected['execution_screen'].get('all_admissible_Q_n_s'),
     'candidate_labels_at_first_decision':selected['execution_screen'].get('all_admissible_action_labels')}
    rows.append(row)
    checkpoint=save_checkpoint(directory/f'checkpoint_after_{repetition:02d}.pkl.z',context,rows,provenance_sha)
    checkpoint['absolute_path']=str(directory/checkpoint['path']);row['end_checkpoint']=checkpoint
    # Train a NEW immutable object from copied completed-repetition data. A
    # prior model includes only other TRAIN conditions + current online rows.
    if pending is None:
     online_X=np.asarray([r['features'] for r in learning_rows]);online_y=np.asarray([r['return_full_n_s'] for r in learning_rows])
     if mode=='PRIOR':
      # Equal condition-level importance; repeated online rows personalize the
      # prior but are explicitly logged, never described as from-scratch.
      X=np.vstack([X_prior,np.repeat(online_X,8,axis=0)]);y=np.r_[y_prior,np.repeat(online_y,8)]
     else:X=online_X;y=online_y
     path=directory/'models'/f'candidate_after_rep_{repetition:02d}.npz'
     pending=pool.submit(train_update,X.copy(),y.copy(),names,kind,path,{'mode':mode,'condition':condition,'after_repetition':repetition,'online_rows':len(online_X),'prior_rows':len(X_prior) if mode=='PRIOR' else 0,'continuation_policy_provenance_retained':True,'ridge_regularization_alpha':latency_configuration.get('ridge_regularization_alpha',10.)})
     try:
      result=pending.result(timeout=2.);updates.append({**result,'stage':'update_prepared','after_repetition':repetition,'ready_within_bound':True})
      # Promotion still occurs only at the NEXT explicit settled boundary.
     except TimeoutError:updates.append({'stage':'update_pending','after_repetition':repetition,'wait_bound_s':2.,'continue_with_previous_validated_model':True})
     except Exception as error:
      updates.append({'stage':'update_failed_previous_model_retained','after_repetition':repetition,'error':str(error)});pending=None
   else:
    rows.append({'session_id':output_tag,'repetition_index':repetition,'condition_id':condition,'mode':mode,'run_id':run_id,'status':record['status'],'failure_reason':record.get('failure_reason'),'failure_transition_not_a_low_cost_return':True})
    # Preserve failed session and continue on a fresh development session only
    # if the native boundary cannot legally return; no state teleport occurs.
    try:advance_inter_rep_boundary(context,max_wait_s=2.)
    except Exception as error:
     rows[-1]['continuous_session_ended_reason']=str(error);context={};runner.SESSION_CONTEXT=context
   archive_outputs(out,RAW)
   rows[-1]['scientific_harness_inter_rep_processing_wall_s']=time.perf_counter()-processing_start
   rows[-1]['processing_scope']='return extraction, checkpoint, bounded model readiness wait, scientific artifact archival; safe boundary and next runtime initialization separate'
   save(directory/'per_repetition.json',rows);save(directory/'training_updates.json',updates)
   print(json.dumps({'pilot':output_tag,'rep':repetition,'status':rows[-1]['status'],'cost':rows[-1].get('J_F_task_n_s'),'descriptor':rows[-1].get('selected_continuation'),'model':rows[-1].get('model_version_used')}),flush=True)
 finally:
  pool.shutdown(wait=True)
  if pending is not None and pending.done():
   try:updates.append({**pending.result(),'stage':'final_prepared_not_promoted_without_next_boundary'})
   except Exception as error:updates.append({'stage':'final_update_failed_previous_model_retained','error':str(error)})
  save(directory/'training_updates.json',updates);runner.SESSION_CONTEXT=None
 return {'session':output_tag,'mode':mode,'condition':condition,'rows':rows,'training_updates':updates,'path':str(directory.relative_to(R)),'continuous_context_persisted':True,'scope':provenance['scope']}

def main(condition='sync_120',tag='v1',resume=False):
 gate=json.loads((D/'OFFLINE_MODEL_PROMOTION_GATE.json').read_text())
 if gate['status']!='PASS':raise RuntimeError('offline meaningful ranking gate not passed')
 latency=json.loads((D/'ONLINE_LATENCY_PROMOTION_GATE.json').read_text())
 if latency['status']!='PASS':raise RuntimeError('online computation has no plausible path; pilot gate closed')
 manifest=json.loads((D/'VALUE_DATASET_MANIFEST.json').read_text())
 with np.load(R/manifest['dataset_path']/'data.npz',allow_pickle=False) as f:
  mask=(f['split']=='train')&(f['condition']!=condition);prior_data=(f['X'][mask].copy(),f['y_full'][mask].copy())
 chosen_model=load_model(gate['chosen_model']);kind=chosen_model.kind
 latency.setdefault('pilot_configuration',{})['ridge_regularization_alpha']=chosen_model.metadata.get('regularization_alpha',10.)
 plan={'schema':'small_online_pilot_plan_v1','status':'FROZEN_BEFORE_PILOT','condition':condition,'initialization_modes':['SCRATCH','PRIOR'],'prior_training_excludes':condition,'value_model':kind,'proposal_bank':BANK,'max_repetitions':8,'active_model_immutable_within_rep':True,'promotion_only_at_explicit_settled_repetition_boundary':True,'update_wait_bound_s':2.,'convergence_thresholds':'derive only after this pilot; no forced rep5 freeze','scope':'one next-target decision commits temporally coherent explicit continuation; all later targets execute with live state/reference/controller/safety'}
 if not resume:save(D/'ONLINE_PILOT_PLAN.json',plan)
 results=[]
 for mode in ('SCRATCH','PRIOR'):
  result=run_mode(mode,condition,kind,prior_data,mode.lower()+'_'+tag,latency.get('pilot_configuration',{}),resume=resume);results.append(result)
  save(D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json',{'schema':'small_online_pilot_v1','status':'RUNNING','sessions':results})
 output={'schema':'small_online_pilot_v1','status':'COMPLETE','sessions':results,'maximum_repetitions':8,'no_final_30rep_experiment':True,'no_hardware_or_realtime_qualification':True}
 save(D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json',output)
 (D/'ONLINE_POLICY_IMPROVEMENT_PILOT.md').write_text('# Small online policy-improvement pilot\n\n'+json.dumps(output,indent=2)+'\n')
 save(D/'SCRATCH_VS_PRIOR_ANALYSIS.json',{'schema':'scratch_vs_prior_v1','sessions':results,'scratch_no_cross_condition_pretrained_value':True,'prior_excludes_current_condition':True,'common_known_proposal_repertoire':True,'caution':'This tests value initialization, not learning controller/task/safety or candidate families from nothing; no five-shot-from-scratch claim for PRIOR'})
 timings=json.loads((D/'TRAINING_UPDATE_LATENCY.json').read_text());timings['repetition_boundary_updates']=[u for result in results for u in result['training_updates']];save(D/'TRAINING_UPDATE_LATENCY.json',timings)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--condition',default='sync_120');p.add_argument('--tag',default='v1');p.add_argument('--resume',action='store_true');a=p.parse_args();main(a.condition,a.tag,a.resume)
