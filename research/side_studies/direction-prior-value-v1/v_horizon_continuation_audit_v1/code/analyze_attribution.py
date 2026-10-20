from audit_common import *
from analyze_diagnostics import metric_extra
import numpy as np
def selected(rows):
 result=[]
 for row in rows:
  accepted=[c for c in row['candidates'] if not c['rejected']]
  best=min(accepted,key=lambda c:c['score']) if accepted else None
  result.append(dict(task_s=row['context']['task_s'],phase=row['context']['phase'],counts=row['count_before'],identity=None if best is None else [best['generation'],best['index'],best['source']],plan_hash=hashlib.sha256(np.asarray(row['selected_plan'],float).tobytes()).hexdigest(),plan=row['selected_plan'],accepted_ranking=[[c['generation'],c['index'],c['source'],c['score']] for c in sorted(accepted,key=lambda c:c['score'])],decision_wall_s=row['decision_wall_s'],candidate_count=len(row['candidates'])))
 return result
def main():
 pairs=[]
 for group in range(4):
  records={};search={};extras={}
  for condition in ('EST','KNOWN'):
   name=f'100_attribution_{group}_{condition}';path=STUDY/'output'/(name+'_RESULT.json')
   if not path.exists():continue
   result=read(path)
   if result['status']!='COMPLETE':records[condition]=result;continue
   records[condition]=result;search[condition]=read(STUDY/'output'/(name+'_SEARCH.json'));extras[condition]=metric_extra(result['metric'],STUDY)[0]
  if len(search)<2:continue
  a,b=records['EST']['metric'],records['KNOWN']['metric'];checks={key:np.array_equal(a[key],b[key]) for key in ('model_beta','model_residual','initial_estimated_state','initial_reference')}
  paths=[STUDY/'source'/records[c]['metric']['trace'] for c in ('EST','KNOWN')]
  with np.load(paths[0]) as za,np.load(paths[1]) as zb:
   for field in ('time_s','physics_steps','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','cr12_q_rad','cr12_dq_rad_s','physical_cuff_position_world_m','physical_cuff_rotation_world','physical_cuff_force_world_n','physical_cuff_moment_world_nm'):
    va=za[field][za['stage']!='TASK'];vb=zb[field][zb['stage']!='TASK'];checks['commissioning_'+field]=np.array_equal(va,vb)
  sr={c:selected(search[c]['rows']) for c in ('EST','KNOWN')};initial1=search['EST']['rows'][0]['candidates'][:8];initial2=search['KNOWN']['rows'][0]['candidates'][:8]
  checks['first_generation_candidate_plans']=all(x['plan']==y['plan'] for x,y in zip(initial1,initial2));checks['candidate_budget']=all(r['candidate_count']==16 for c in sr for r in sr[c]);checks['no_network']=all(search[c]['network_calls']==0 for c in search);checks['same_seed']=records['EST']['inputs']['seed']==records['KNOWN']['inputs']['seed']
  checks['first_research_context_exact']=search['EST']['rows'][0]['context']==search['KNOWN']['rows'][0]['context'];checks['first_research_counts_exact']=search['EST']['rows'][0]['count_before']==search['KNOWN']['rows'][0]['count_before'];checks['same_legal_prefix']=records['EST']['inputs']['prefix']==records['KNOWN']['inputs']['prefix']
  pair=dict(group=group,kind='nominal' if group<2 else 'deviation',qualified=all(records[c]['metric']['valid'] and records[c]['metric']['matched_eligible'] and records[c]['metric']['status']=='COMPLETE' for c in records) and all(checks.values()),controls=checks,P_EST_J_F=a['J_F'],P_KNOWN_J_F=b['J_F'],KNOWN_EFFECTIVE_PARAM_EFFECT_Ns=a['J_F']-b['J_F'],KNOWN_EFFECTIVE_PARAM_EFFECT_fraction=(a['J_F']-b['J_F'])/a['J_F'],moment_change_fraction=(b['moment_integral']-a['moment_integral'])/a['moment_integral'],metrics={c:{**records[c]['metric'],**extras[c]} for c in records},selected_candidates=sr,decision_times={c:[r['decision_wall_s'] for r in sr[c]] for c in sr},parameters={c:read(STUDY/'output'/(f'100_attribution_{group}_{c}_PARAMETERS.json')) for c in records})
  known=read(STUDY/'output/KNOWN_MODEL_PARAMETERS.json')
  differences=[y['prediction']['total_cost']-x['prediction']['total_cost'] for x,y in zip(initial1,initial2)]
  pair['first_generation_known_minus_est_cost_range_Ns']=[min(differences),max(differences)]
  pair['research_beta_source_contrast_norm']=float(np.linalg.norm(np.asarray(pair['parameters']['KNOWN']['beta'])-np.asarray(pair['parameters']['EST']['beta'])))
  pair['selected_plans_all_equal']=len(sr['EST'])==len(sr['KNOWN']) and all(x['plan_hash']==y['plan_hash'] and x['phase']==y['phase'] and x['counts']==y['counts'] for x,y in zip(sr['EST'],sr['KNOWN']))
  for condition in ('EST','KNOWN'):pair['parameters'][condition]['research_geometry']=pair['parameters'][condition]['estimated_geometry'] if condition=='EST' else known['geometry'];pair['parameters'][condition]['research_residual_weights_fixed']=np.zeros((2,5)).tolist()
  path=STUDY/'output'/(f'110_B_reference_{group}_RESULT.json')
  if path.exists() and read(path)['status']=='COMPLETE':
   baseline=read(path);bm=baseline['metric'];valid=bool(bm['valid'] and bm['matched_eligible']);controls={key:np.array_equal(bm[key],a[key]) for key in ('model_beta','model_residual','initial_estimated_state','initial_reference')};controls['same_seed']=baseline['inputs']['seed']==records['EST']['inputs']['seed'];controls['same_legal_prefix']=baseline['inputs']['prefix']==records['EST']['inputs']['prefix']
   baseline_path=STUDY/'source'/bm['trace']
   with np.load(baseline_path) as z0,np.load(paths[0]) as z1:
    for field in ('time_s','physics_steps','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','cr12_q_rad','physical_cuff_position_world_m','physical_cuff_force_world_n','physical_cuff_moment_world_nm'):
     controls['commissioning_'+field]=np.array_equal(z0[field][z0['stage']!='TASK'],z1[field][z1['stage']!='TASK'])
    stop=float(z1['time_s'][z1['stage']=='TASK'][0])+search['EST']['rows'][0]['context']['task_s']
    for field in ('time_s','physics_steps','estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','cr12_q_rad','physical_cuff_force_world_n','physical_cuff_moment_world_nm'):
     controls['through_common_prefix_'+field]=np.array_equal(z0[field][z0['time_s']<=stop+1e-8],z1[field][z1['time_s']<=stop+1e-8])
   assert all(controls.values()),('B_REFERENCE_INPUT_MISMATCH',group,controls)
   pair['new_B_reference']=dict(qualified=valid,metric=bm,controls=controls,P_EST_gain_vs_B_fraction=(bm['J_F']-a['J_F'])/bm['J_F'],P_KNOWN_gain_vs_B_fraction=(bm['J_F']-b['J_F'])/bm['J_F'],known_parameter_increment_over_B_fraction=(a['J_F']-b['J_F'])/bm['J_F'],interpretation='new paired B baseline with identical prefix; no historical B/E arithmetic')
  pairs.append(pair)
 qualified=[p for p in pairs if p['qualified']];summary=dict(complete=len(pairs)==4,qualified_pairs=len(qualified),P_EST_mean_J_F=None if not qualified else float(np.mean([p['P_EST_J_F'] for p in qualified])),P_KNOWN_mean_J_F=None if not qualified else float(np.mean([p['P_KNOWN_J_F'] for p in qualified])),mean_paired_effect_fraction=None if not qualified else float(np.mean([p['KNOWN_EFFECTIVE_PARAM_EFFECT_fraction'] for p in qualified])),mean_paired_moment_change_fraction=None if not qualified else float(np.mean([p['moment_change_fraction'] for p in qualified])),claim='KNOWN_EFFECTIVE_PARAM_EFFECT; controlled change of research beta/geometry parameter source only; not evidence about a deployable identifier improvement')
 save(STUDY/'HUMAN_MODEL_ATTRIBUTION.json',dict(summary=summary,pairs=pairs));print(json.dumps(summary))
if __name__=='__main__':main()
