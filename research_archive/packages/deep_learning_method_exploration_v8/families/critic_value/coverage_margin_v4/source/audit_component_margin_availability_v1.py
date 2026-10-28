"""A4仅恢复已存MEASURED原45分量margin；不重算轨迹/模型、不fit。"""
from pathlib import Path
import hashlib
import json
import math
import resource
import time
P=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8');R=P/'families/critic_value/coverage_margin_v4'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def put(p,d):
 with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def components(a,b,pr):
 values=[]
 def add(name,group,margin,unit,source,denominator):
  assert finite(margin) and finite(denominator) and denominator>0
  values.append({'name':name,'original_failed_requirement_group':group,'signed_normalized_margin':margin,'source_paths':source,'original_value_units':unit,'normalization_denominator':denominator})
 for signal,key in [('velocity_deg_s','velocity'),('acceleration_deg_s2','acceleration'),('jerk_deg_s3','jerk')]:
  for metric in pr[key]:
   av,bv=a['motion']['raw']['full'][signal][metric],b['motion']['raw']['full'][signal][metric]
   assert len(av)==len(bv)==2
   for j,(x,y) in enumerate(zip(av,bv)):
    den=max(abs(y),1e-12);add(signal+'/'+metric+'/'+str(j),signal+'/'+metric,(y*pr['burden_ratio']+1e-7-x)/den,signal,['motion.raw.full.'+signal+'.'+metric+'.'+str(j)],den)
 da,db=a['dose'],b['dose'];limit=pr['excursion_abs_delta_deg']
 for j in range(2):add('excursion/'+str(j),'excursion',(limit+1e-7-abs(da['excursion_deg'][j]-db['excursion_deg'][j]))/limit,'deg',['dose.excursion_deg.'+str(j)],limit)
 for j in range(2):
  ratio=da['cumulative_travel_deg'][j]/db['cumulative_travel_deg'][j];upper=pr['cumulative_ratio_upper'];lower=pr['cumulative_ratio_lower']
  add('travel_upper/'+str(j),'cumulative_dose',(upper+1e-7-ratio)/(upper-1),'ratio',['dose.cumulative_travel_deg.'+str(j)],upper-1)
  add('travel_lower/'+str(j),'cumulative_dose',(ratio-lower+1e-7)/(1-lower),'ratio',['dose.cumulative_travel_deg.'+str(j)],1-lower)
 limit=pr['endpoint_and_phase_boundary_abs_delta_deg']
 for j in range(2):add('endpoint/'+str(j),'endpoint_phase_boundary',(limit+1e-7-abs(da['endpoint_deg'][j]-db['endpoint_deg'][j]))/limit,'deg',['dose.endpoint_deg.'+str(j)],limit)
 for phase in ['OUTBOUND','HOLD','RETURN']:
  for boundary in ['start_deg','end_deg']:
   for j in range(2):add('phase_boundary/'+phase+'/'+boundary+'/'+str(j),'endpoint_phase_boundary',(limit+1e-7-abs(da['phase_boundaries'][phase][boundary][j]-db['phase_boundaries'][phase][boundary][j]))/limit,'deg',['dose.phase_boundaries.'+phase+'.'+boundary+'.'+str(j)],limit)
 limit=pr['total_duration_abs_delta_s'];add('task_duration','task_duration',(limit+1e-8-abs(da['duration_s']-db['duration_s']))/limit,'s',['dose.duration_s'],limit)
 for phase in ['OUTBOUND','HOLD','RETURN']:
  limit=pr['each_phase_duration_abs_delta_s'];add('phase_duration/'+phase,phase+'_duration',(limit+1e-8-abs(a['phase_durations'][phase]-b['phase_durations'][phase]))/limit,'s',['phase_durations.'+phase],limit)
 for field,limit_key,unit in [('moment_integral_Nm_s','moment_integral_ratio','Nm*s'),('force_peak_N','force_peak_ratio','N'),('moment_peak_Nm','moment_peak_ratio','Nm')]:
  den=max(abs(b[field]),1e-12);add(field,field,(b[field]*pr[limit_key]+1e-7-a[field])/den,unit,[field],den)
 limit=pr['tracking_RMS_add_deg']
 for j in range(2):add('tracking/'+str(j),'tracking',(b['tracking_RMS_deg'][j]+limit+1e-7-a['tracking_RMS_deg'][j])/limit,'deg',['tracking_RMS_deg.'+str(j)],limit)
 assert len(values)==45 and len({v['name'] for v in values})==45
 return values

def main():
 start=time.time();cpu=resource.getrusage(resource.RUSAGE_SELF)
 A2=P/'families/critic_value/coverage_risk_v2/data/ACTUAL_COVERAGE_DATASET_V1.json';A3=P/'families/critic_value/coverage_state_v3/data/STATE_JOINED_DATASET_V1.json'
 assert sha(A2)=='e7a54dd7d3d39f0ab94cec45ceea284d6efec51d186ab74e46ff2335e82b79e0'
 assert sha(A3)=='54b017803ae55575e1284dda2156d7534eaa9a2ebb6796d512709b439a2e863a'
 old=load(A2);joined=load(A3);context={r['group']:r['context'] for r in joined['rows']}
 protocol_path=P/'runtime/MOTION_ACCEPTANCE_PROTOCOL.json';protocol=load(protocol_path);pr=protocol['primary'];files={str(A2):sha(A2),str(A3):sha(A3),str(protocol_path):sha(protocol_path)};rows=[];errors=[];audits=[]
 for oldrow in old['rows']:
  assert time.time()-start<90
  try:
   source=P.parent/oldrow['source_result'];package=source.parents[1];raw=load(source);Brow=next(r for r in old['rows'] if r['group']==oldrow['group'] and r['action_recipe']['action']['family']=='B');Bsource=P.parent/Brow['source_result'];Braw=load(Bsource)
   mpath=package/raw['metrics_path'];bpath=package/Braw['metrics_path'];a,b=load(mpath),load(bpath)
   assert raw['complete'] is True and raw['error'] is None and Braw['complete'] is True and Braw['qualified'] is True
   assert raw['branch']['full_hash']==Braw['branch']['full_hash']==oldrow['parent_evaluation_only']['snapshot_full_hash']
   assert a['branch']['full_hash']==b['branch']['full_hash']==raw['branch']['full_hash']
   assert sha(package/'runtime/MOTION_ACCEPTANCE_PROTOCOL.json')==sha(protocol_path)
   assert raw['JF']==oldrow['labels_evaluation_only']['JF_N_s']==a['J_F_N_s'] and raw['JM']==oldrow['labels_evaluation_only']['JM_Nm_s']==a['moment_integral_Nm_s']
   values=components(a,b,pr);negative={v['original_failed_requirement_group'] for v in values if v['signed_normalized_margin']<0}
   original=raw['motion_vs_B'];axesfail=set()
   if a['axes']['PHYSICAL_TASK_VALID']!='PASS':axesfail.add('physical_task')
   if a['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']!='PASS':axesfail.add('causal_ownership')
   assert negative|axesfail==set(original['failed_requirements']),(raw['id'],negative,original['failed_requirements'])
   assert original['acceptance_pass']==(not negative and not axesfail)
   assert raw['qualified']==(original['acceptance_pass'] and a['axes']['LEGACY_R2_MATCHED']=='PASS' and a['native_physical_audit']['pass_'] and not axesfail)
   for f in [source,Bsource,mpath,bpath,package/'runtime/MOTION_ACCEPTANCE_PROTOCOL.json',package/'runtime/code/explore_common.py',package/'runtime/code/analyze_matched.py']:files[str(f)]=sha(f)
   rows.append({'id':raw['id'],'group_evaluation_only':oldrow['group'],'split_parent_group_evaluation_only':oldrow['split_parent_group_evaluation_only'],'context':context[oldrow['group']],'action_recipe':oldrow['action_recipe'],'action_recipe_sha256':oldrow['action_recipe_sha256'],
    'labels_evaluation_only':{'signed_normalized_original_45_margin':[v['signed_normalized_margin'] for v in values],'component_descriptors':values,'JF_N_s':raw['JF'],'JM_Nm_s':raw['JM'],'delta_JF_N_s':raw['JF']-Braw['JF'],'delta_JM_Nm_s':raw['JM']-Braw['JM'],'original_qualified':raw['qualified'],'original_motion_failed_requirements':original['failed_requirements'],'original_axes':a['axes'],'native_hard_audit_pass':a['native_physical_audit']['pass_']},
    'provenance_evaluation_only':{'result_path':str(source),'result_sha256':sha(source),'MEASURED_path':str(mpath),'MEASURED_sha256':sha(mpath),'same_parent_B_result_path':str(Bsource),'same_parent_B_result_sha256':sha(Bsource),'B_MEASURED_path':str(bpath),'B_MEASURED_sha256':sha(bpath),'parent_fingerprint':raw['branch']['full_hash'],'protocol_sha256':sha(protocol_path)},'whole_raw77_still_invalid':True,'TASK_values_are_labels_not_inputs':True})
   audits.append({'id':raw['id'],'components':45,'finite':True,'same_actual_parent_B':True,'exact_original_motion_failed_groups_parity':True,'no_native_truth_features':True})
  except Exception as e:errors.append({'id':oldrow['id'],'error':str(e),'missing_not_imputed':True})
 data={'schema':'v8.a4.original_component_margin_data.v1','rows':rows,'component_names':rows[0]['labels_evaluation_only']['component_descriptors'] if rows else [],'source_A2_SHA':sha(A2),'source_A3_SHA':sha(A3),'input_source_profiles':joined['input_source_profiles'],'input_source_profile_paths':joined['input_source_profile_paths'],'all_contexts_development_exposed':True,'original_thresholds_and_tolerances_unchanged':True,'phase_shape_diagnostic_excluded_from45':True,'source_TASK_truth_used_only_as_target_labels':True,'new_fit_or_forward_or_physics':0}
 put(R/'data/ORIGINAL_MARGIN_DATASET_V1.json',data)
 final=resource.getrusage(resource.RUSAGE_SELF);audit={'status':'ALL_48_AVAILABLE' if len(rows)==48 and not errors else 'MISSING_UNIMPUTED','rows':len(rows),'parents':len({r['split_parent_group_evaluation_only'] for r in rows}),'components_per_row':45,'errors':errors,'row_audits':audits,'files_sha256':files,'dataset_sha256':sha(R/'data/ORIGINAL_MARGIN_DATASET_V1.json'),'wall_s':time.time()-start,'CPU_user_s':final.ru_utime-cpu.ru_utime,'CPU_system_s':final.ru_stime-cpu.ru_stime,'RSS_peak_KiB':final.ru_maxrss,'new_model_init_forward_fit_physics':0,'sealed_or_active_H2_reads':0}
 put(R/'analysis/AVAILABILITY_AUDIT_V1.json',audit);print(json.dumps({k:audit[k] for k in ['status','rows','parents','components_per_row','errors','dataset_sha256','wall_s','CPU_user_s','CPU_system_s','RSS_peak_KiB']},ensure_ascii=False))
if __name__=='__main__':main()
