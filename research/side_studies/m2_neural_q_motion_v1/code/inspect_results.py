from research_common import *
e=load(OUT/'NEURAL_Q_EVALUATION.json');m=load(OUT/'MOTION_BURDEN_AUDIT.json')
for name,a in e['models'].items():
 for g in a['test']['groups']:print(name,g['snapshot'][:10],'chosen',g['selected_id'],'best',g['best_ids'],'regret',g['regret_N_s'])
print('SENSITIVITY',[(r['model'],r['ratio'],r.get('selected_id')) for r in e['motion_filter_sensitivity']])
print('PROBES',e['interaction_probes']);print('LATENCY',e['inference'])
for pair in m['pairs']:
 audits=[load(OUT/'motion_series'/f"{pair['package']}_{pair[k]}_AUDIT.json") for k in ['B_id','M2_id']]
 print('MOTION',pair['B_id'],'samples',[r['quality']['native_samples'] for r in audits],'excursion_delta',pair['angle_excursion_delta_deg'],'time',pair['duration_delta_s'])
 for fil in ['raw','savgol_5','savgol_21']:
  print(fil,'knee_max_velocity', [r['actual_human'][fil]['full']['velocity_deg_s']['max_abs'][1] for r in audits], 'knee_p95_a',[r['actual_human'][fil]['full']['acceleration_deg_s2']['p95_abs'][1] for r in audits])
old=Path('/home/hank/coding/adaptive-traction-mpc-learning/stages/stage5_personalized_motion_learning/docs/value_learning_research_v1/OFFLINE_VALUE_MODEL_COMPARISON.json')
j=load(old)
for k,a in j['selected_models'].items():print('HIST96',k,'val',a['validation_full_action_ranking']['mean_regret_n_s'],'test',a['test_full_action_ranking']['mean_regret_n_s'],'testtop1',a['test_full_action_ranking']['top1_accuracy'],'testrmse',a['test_target_prediction']['RMSE_n_s'])
print('START',load(OUT/'PRESERVATION_BEFORE.json')['start_unix'],'NOW',time.time())
