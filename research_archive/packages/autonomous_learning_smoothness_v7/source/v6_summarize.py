from pathlib import Path
import json,time,hashlib,os
import numpy as np
P=Path(__file__).resolve().parents[1]
def read(n,default=None):
 f=P/n;return json.loads(f.read_text()) if f.exists() else default

def put(n,x):f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def bucket(g):
 if g.startswith(('TRAIN_','DEV_')):return 'CORE'
 if g.startswith(('COORD_R','PHASE_RULE_')) or g in ['SCREEN_S1','SCREEN_S2','RULE_DEV']:return 'ADAPTIVE'
 return 'LOCKED_VALIDATION'
def account():
 events=[json.loads(s) for s in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in events if r['event']=='START'];ends={r['id']:r for r in events if r['event']=='END'};rows=[]
 for s in starts:
  ident=s['id'];data=read('runtime/output/'+ident+'_DATA.json');partial=read('runtime/output/'+ident+'_PARTIAL_COMPUTE.json');result=read('attempts/'+ident+'_RESULT.json');value=data['metric'] if data else partial or {};steps=value.get('actual_new_native_physics_steps');rows.append(dict(id=ident,group=s.get('group'),budget_bucket=bucket(s.get('group','')),kind=s.get('kind'),START_unix=s['unix'],END_unix=ends.get(ident,{}).get('unix'),returncode=ends.get(ident,{}).get('returncode'),actual_new_native_steps=steps,complete_raw=bool(data),original_qualified=None if result is None else result['qualified'],raw_task_valid=value.get('task_valid'),failed_requirements=None if result is None else result.get('motion_vs_B',{}).get('failed_requirements'),error=(result or {}).get('error') or ends.get(ident,{}).get('error'),source_manifest_sha256=s.get('job_source_sha256'),config_sha256=s.get('config_sha256')))
 buckets={b:dict(physical_START=sum(r['budget_bucket']==b for r in rows),actual_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in rows if r['budget_bucket']==b)) for b in ['CORE','ADAPTIVE','LOCKED_VALIDATION']};jobs=[]
 for f in sorted((P/'owned').glob('*_SUPERVISOR_END.json')):
  d=json.loads(f.read_text());jobs.append(dict(group=f.name[:-20],wall_s=d['wall_s'],exit_code=d['worker_exit_code']))
 end=read('END.json',{});act=read('ACTIVATION.json');out=dict(status='ALL_STARTED_ATTEMPTS_ACCOUNTED' if len(ends)==len(starts) and all(r['actual_new_native_steps'] is not None for r in rows) else 'IN_PROGRESS_OR_MISSING',activation=act,updated_unix=time.time(),elapsed_wall_s=end.get('elapsed_seconds',time.time()-act['T0_unix']),physical_START=len(starts),physical_END=len(ends),actual_new_native_steps=sum(r['actual_new_native_steps'] or 0 for r in rows),actual_new_simulation_seconds=.00025*sum(r['actual_new_native_steps'] or 0 for r in rows),native_dt_s=.00025,cold_parent_episodes=sum(r['kind']=='LEGAL_COLD_PARENT' for r in rows),candidate_complete_raw=sum(r['complete_raw'] and r['kind']!='LEGAL_COLD_PARENT' for r in rows),candidate_qualified=sum(r['original_qualified'] is True for r in rows),candidate_motion_failed_ids=[r['id'] for r in rows if r['original_qualified'] is False and r['complete_raw']],partial_or_missing_raw_ids=[r['id'] for r in rows if not r['complete_raw']],intentional_prefix_sampler_ids=[r['id'] for r in rows if ends.get(r['id'],{}).get('expected_prefix_sampler_completion')],unexpected_incomplete_ids=[r['id'] for r in rows if not r['complete_raw'] and not ends.get(r['id'],{}).get('expected_prefix_sampler_completion')],budget_buckets=buckets,attempts=rows,jobs=jobs,new_PPO_training_episodes=0,new_PPO_gradient_updates=0,critic_full_menu_attempt_savings=0,historical_sunk_cost={'v5_START':189,'v5_native_steps':12889360,'initial_risk_rows_reused':53,'expanded_risk_windows':read('models/WHOLE_HISTORY_RISK_V5_FROZEN.json',{}).get('rows'), 'risk_failure_state_families':read('models/WHOLE_HISTORY_RISK_V5_FROZEN.json',{}).get('positive_state_families'),'new_training_cost_not_free':True},fit_resources=read('models/COMMON_COMPOSE_FROZEN.json',{}).get('fit_resources'),risk_replay_resources=read('audit/RISK_FIT_REPLAY_AND_COST.json',{}).get('replay_fit_resources'),expanded_risk_preprocessing_and_CV_resources=read('models/WHOLE_HISTORY_RISK_V5_FROZEN.json',{}).get('fit_resources'),prescreen_fit_resources={k:read('models/PRESTATE_PROXY_'+k+'_FROZEN.json',{}).get('fit_resources') for k in ['V1','V2']},sampling='MuJoCo dynamics, not hardware/patients; inherited prefixes not recharged as new native integration')
 resources=[]
 for f in (P/'logs').glob('*_RESOURCES.jsonl'):
  resources += [json.loads(s) for s in f.read_text().splitlines()]
 if resources:out.update(minimum_available_ram_gib=min(r['available_ram_bytes'] for r in resources)/2**30,minimum_free_disk_gib=min(r['disk_free_bytes'] for r in resources)/2**30)
 out['additional_read_only_audit_resources']={'causal_receipt_and_truncation_audit':read('audit/CAUSAL_EVENT_AVAILABILITY_AND_TRUNCATION.json',{}).get('resources')}
 out['first_complete_task_server_timing']=read('audit/FULL_TASK_SERVER_TIMING.json',{})
 inverse_counts={}
 for r in rows:
  d=read('runtime/output/'+r['id']+'_DATA.json');part=read('runtime/output/'+r['id']+'_PARTIAL_COMPUTE.json',{});v=d['metric'] if d else part
  inverse_counts[r['id']]=v.get('actual_new_main_model_inverse_dynamics_api_calls')
  r['actual_new_main_inverse_dynamics_api_calls']=inverse_counts[r['id']]
 out['actual_new_main_inverse_dynamics_api_calls']=sum(x or 0 for x in inverse_counts.values())
 out['inverse_dynamics_api_count_missing_ids']=[k for k,v in inverse_counts.items() if v is None]
 out['measurement_limits']={'physics_CPU_seconds':'NOT_INSTRUMENTED; native steps and actual job wall measured, no fabricated CPU total','wall_overlap':'cold parents wait while forked candidates execute; do not sum attempt wall intervals as campaign elapsed','RAM_disk':'minimum system availability at supervisor samples, not per-process peak RSS or a cgroup allocation limit','engineering_environment':'unused local .venv/pip bootstrap never used by physical runs; shared preexisting scientific environment identity audited'}
 put('RESOURCE_AND_ATTEMPT_ACCOUNTING.json',out);return out

def blend():
 out=[]
 for g in ['DEV_O1','SMOOTH_A1','SMOOTH_A2']:
  data=read('data/'+g+'.json',[]);rows={r['tag']:r for r in data if r['horizon_s']==.5}
  if not all(t in rows for t in ['BEST','COMPOSE','BLEND']):continue
  b,c,x=(rows[t] for t in ['BEST','COMPOSE','BLEND']);bv=np.r_[b['metrics']['full_jerk_RMS_deg_s3'],b['metrics']['wrench']['force_norm_rate_RMS_N_s']];cv=np.r_[c['metrics']['full_jerk_RMS_deg_s3'],c['metrics']['wrench']['force_norm_rate_RMS_N_s']];xv=np.r_[x['metrics']['full_jerk_RMS_deg_s3'],x['metrics']['wrench']['force_norm_rate_RMS_N_s']];ret=np.where(bv-cv>1e-12,(bv-xv)/(bv-cv),0.)
  out.append(dict(group=g,role='development' if g=='DEV_O1' else 'independent frozen confirmation',all_three_original_qualified=all(r['qualified'] for r in [b,c,x]),BLEND_JF_reduction_vs_COMPOSE=c['metrics']['full_JF']-x['metrics']['full_JF'],BLEND_JM_increase_vs_COMPOSE=x['metrics']['full_JM']-c['metrics']['full_JM'],BLEND_vs_BEST_percent=((xv/bv-1)*100).tolist(),COMPOSE_vs_BEST_percent=((cv/bv-1)*100).tolist(),retained_fraction_of_COMPOSE_improvement_hip_knee_force_rate=ret.tolist(),retention_90pct_pass=bool(np.all(ret>=.9)),original_costs={t:dict(qualified=rows[t]['qualified'],JF=rows[t]['metrics']['full_JF'],JM=rows[t]['metrics']['full_JM']) for t in ['BEST','COMPOSE','BLEND']}))
 for r in out:r['COMPOSE_and_BLEND_original_qualified']=all(r['original_costs'][t]['qualified'] for t in ['COMPOSE','BLEND'])
 put('analysis/BLEND_FIXED_CONFIRMATION_RESULTS.json',out);return out

def screens():
 rows=[];gross_unique_omitted=0;raw_tag_omitted=0
 for g in ['SCREEN_S1','SCREEN_S2','SCREEN_S3','SCREEN_AUDIT']:
  pred=read('predictions/'+g+'_PRESTATE_SCREEN.json');data=read('data/'+g+'.json',[])
  if not pred or not data:continue
  half={r['tag']:r for r in data if r['horizon_s']==.5};selected=half.get(pred['choice']);executed=[t for t in pred['unique_menu'] if t in half];omitted=[t for t in pred['unique_menu'] if t not in half];tags=[t for t in pred['original_menu'] if t not in half];s=read('runtime/ATTEMPTS.jsonl') if False else None
  if g!='SCREEN_AUDIT':gross_unique_omitted+=len(omitted);raw_tag_omitted+=len(tags)
  qualified=[r for t,r in half.items() if t in pred['unique_menu'] and r['qualified']];best=min(qualified,key=lambda r:r['labels']['full_remaining_JF']) if qualified else None
  events=[json.loads(l) for l in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];first=min(r['unix'] for r in events if r['event']=='START' and r['id'].startswith(g+'_') and r['id'] in [g+'_'+tag for tag in pred['unique_menu']]);assert pred['created_unix']<first,'SCREEN_USED_PHYSICS_BEFORE_RANKING'
  rows.append(dict(group=g,choice=pred['choice'],qualified=None if selected is None else selected['qualified'],choice_full_JF=None if selected is None else selected['metrics']['full_JF'],choice_full_JM=None if selected is None else selected['metrics']['full_JM'],actual_unique_candidate_full_runs=len(executed),actual_START_including_parent_and_B=sum(r['event']=='START' and r.get('group')==g for r in events),omitted_unique_candidate_identities=omitted,raw_omitted_tags=tags,aliases=pred['aliases'],exhaustive_unique_reference_candidate_runs=len(pred['unique_menu']),ranking_saved_before_any_candidate_START=True,ood_fallback=pred['ood_fallback'],ood_distance=pred['ood_distance'],prediction_wall_s=pred['prediction_wall_s'],total_preselection_wall_s=pred.get('total_preselection_wall_s'),audited_full_menu_best=None if g!='SCREEN_AUDIT' or best is None else best['tag'],audit_regret_N_s=None if g!='SCREEN_AUDIT' or selected is None or best is None or not selected['qualified'] else selected['labels']['full_remaining_JF']-best['labels']['full_remaining_JF'],omitted_outcomes_known=g=='SCREEN_AUDIT'))
 out=dict(status='PROSPECTIVE_SCREENING_EVIDENCE' if rows else 'NOT_RUN',rows=rows,prospectively_omitted_unique_complete_candidate_runs=gross_unique_omitted,raw_tag_omissions=raw_tag_omitted,comparator='prospectively registered enumeration after phase-active alias removal; omitted tails were never executed in screened states',net_research_campaign_attempt_savings_established=False,training_and_audit_overhead='all CORE/ADAPTIVE/LOCKED attempts paid separately; no positive amortized net saving asserted',independent_audit_scope='one separate RETURN state can assess missed quality; omitted tails in screened states remain unobserved',critic_attribution='none; this is a transparent traditional phase-library lookup, not the post-H Critic')
 put('analysis/PROSPECTIVE_SAMPLE_EFFICIENCY.json',out);return out

def evaluations():
 rows=[json.loads(f.read_text()) for f in sorted((P/'analysis/evaluation').glob('*.json'))] if (P/'analysis/evaluation').exists() else [];primary=[r for r in rows if r['group'].startswith('TEST_')];paired={}
 for r in rows:r['independence_role']='TRAINING_PARENT_REPLAY_EXCLUDED_FROM_INDEPENDENT_VALIDATION' if r['group']=='LEGACY_BOUNDARY_O3' and (P/'audit/O3_PARENT_ALIAS_RECLASSIFICATION.json').exists() else 'FROZEN_NEW_PREFIX'
 for k in ['A_FIXED_SMOOTH','B_HALF_SECOND','C_ONE_SECOND','FIXED_TRAINING_CHOICE','GUARD_RULE_HALF','GUARD_RULE_ONE']:
  gains=[r['critic_JF_improvement_vs'][k] for r in primary if r['critic_JF_improvement_vs'][k] is not None];paired[k]=dict(qualified_pairs=len(gains),mean_JF_improvement_N_s=float(np.mean(gains)) if gains else None)
 out=dict(primary_states=len(primary),primary_rows=primary,legacy_rows=[r for r in rows if not r['group'].startswith('TEST_')],paired_summary=paired,critic_qualified_states=sum(r['methods']['D_CRITIC']['qualified'] for r in primary),critic_distinct_physical_choices_vs_training_fixed=sum(r['critic_changes_physical_execution_vs_training_fixed'] for r in primary),meaningful_independent_increment_states=[r['group'] for r in primary if r['methods']['D_CRITIC']['qualified'] and (r['critic_JF_improvement_vs']['C_ONE_SECOND'] or 0)>.02 and (r['critic_JF_improvement_vs']['FIXED_TRAINING_CHOICE'] or 0)>.02],no_model_growth_after_frozen_test=True,independence_scope='whole held-out legal prefix; one nominal Human, not patient-level generalization')
 put('analysis/COMBINED_FROZEN_RESULTS.json',out);return out
if __name__=='__main__':
 a=account();b=blend();s=screens();e=evaluations();print('SUMMARY','START',a['physical_START'],'native',a['actual_new_native_steps'],'tests',e['primary_states'],'blend',len(b),'omitted unique',s['prospectively_omitted_unique_complete_candidate_runs'],flush=True)
