from analyze import *
M=json.loads((P/'RAW_DERIVED_METRICS.json').read_text())['cases'];W=json.loads((P/'FORCE_WINDOWS_AND_CONTRASTS.json').read_text());L=json.loads((P/'LAG_ANALYSIS.json').read_text())['cases']
for x in M:
    if x['label'] in ['B0','18D','legacy005','D1_hip_neg','D1_coupled_inverse','adaptive_D2','S_fixed_knots_late']:
        print('METRIC',x['label'],{k:x[k] for k in ['J_F_N_s','force_peak_N','force_RMS_N','velocity_TV_ratio_vs_B','acceleration_variation_ratio_vs_B','jerk_combined_RMS_ratio_vs_B','moment_integral_Nm_s','tracking_q_deg','jerk_rad_s3']})
for label in ['B0','18D']:
    print('TIME',label,W[label]['time_to_cumulative_fractions_s'])
    print('OVERLAP',label,W[label]['motion_force_overlap'])
    for ph in ['OUTBOUND','RETURN']:
        print('LAGS',label,ph,[{'w':w,'transform':tr,'feat':feat,'r0':L[label][f'{w}|SG0|{ph}|{feat}|{tr}'].get('zero_lag_r'),'peak':L[label][f'{w}|SG0|{ph}|{feat}|{tr}'].get('peak_abs_r'),'lag':L[label][f'{w}|SG0|{ph}|{feat}|{tr}'].get('peak_lag_s')} for w in [.05,.5,1.] for tr in ['level','first_difference'] for feat in FEATURES[:3]])
X=next(x for x in M if x['label']=='18D');rows=W['18D']['half_second_windows'];gain=X['gain_vs_B_N_s'];positive=sum(max(0,r['gain_vs_B_N_s']) for r in rows)
print('18D_CONCENTRATION',{'net':gain,'positive':positive,'top3':sum(r['gain_vs_B_N_s'] for r in W['18D']['largest_gain_windows'][:3]),'top5':sum(r['gain_vs_B_N_s'] for r in W['18D']['largest_gain_windows'][:5]),'4to6':W['18D']['gain_4to6_N_s'],'15to16':W['18D']['gain_15to16_N_s'],'phase':{k:v['J_F_N_s'] for k,v in X['phase_metrics'].items()}})
for name in ['FROZEN_SELECTION.json','EXECUTION_CODE_MANIFEST.json']:
    f=HIST/name
    if f.exists():print('18D_SOURCE',name,str(json.loads(f.read_text()))[:2800])
