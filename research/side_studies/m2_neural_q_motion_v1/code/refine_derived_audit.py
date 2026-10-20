"""Refine derived phase labels and memory accounting; preserve first export."""
from research_common import *
from scipy.signal import savgol_filter
import shutil
history=OUT/'derived_history';history.mkdir(exist_ok=True)
for p in [OUT/'MOTION_BURDEN_AUDIT.json',OUT/'NEURAL_Q_EVALUATION.json']:
 q=history/(p.stem+'_initial.json')
 if not q.exists():shutil.copy2(p,q)
m=load(OUT/'MOTION_BURDEN_AUDIT.json')
for ap in m['run_audit_files']:
 p=Path(ap);r=load(p);base=ROOT/next(pair['package'] for pair in m['pairs'] if r['id'] in [pair['B_id'],pair['M2_id']]);summary=load(base/'source/results'/r['id']/'summary.json')
 with np.load(OUT/'motion_series'/f'{base.name}_{r["id"]}.npz') as f:a={k:f[k].copy() for k in f.files}
 t=a['time_s'];v=a['true_dq_rad_s'];phase=np.full(len(t),'OUTBOUND',dtype='<U15')
 for ev in summary['task']['phase_transitions']:
  if ev['to'] in ['OUTBOUND','HOLD','RETURN']:phase[t>=ev['time_s']-1e-9]=ev['to']
 for win in [0,5,21]:
  vv=v if win==0 else savgol_filter(v,win,3,axis=0,mode='interp');acc=np.gradient(vv,t,axis=0,edge_order=2);jerk=np.gradient(acc,t,axis=0,edge_order=2);signals={'velocity_deg_s':np.rad2deg(vv),'acceleration_deg_s2':np.rad2deg(acc),'jerk_deg_s3':np.rad2deg(jerk)};label='raw' if win==0 else 'savgol_'+str(win)
  r['actual_human'][label]['phases']={ph:{k:stats(b[phase==ph]) for k,b in signals.items()} for ph in ['OUTBOUND','HOLD','RETURN']}
  if win==0:
   for k,events in r['actual_human'][label]['peak_events'].items():
    for ev in events:ev['phase']=str(phase[np.argmin(abs(t-ev['time_s']))])
 r['quality']['phase_definition']='Exact original summary.task.phase_transitions physics timestamps, right-continuous; full native statistics unchanged.'
 r['contact']['sampled_interval_force_integral_sum_N_s']=r['contact'].pop('force_integral_N_s',r['contact'].get('sampled_interval_force_integral_sum_N_s'))
 r['contact']['integral_authority']='native_J_F_N_s is original native integral. Sampled interval sum is a separate diagnostic after duplicate timestamp handling.'
 np.savez_compressed(OUT/'motion_series'/f'{base.name}_{r["id"]}.npz',**{**a,'phase':phase})
 save(str(p.relative_to(OUT)),r)
m['phase_definition']='Original exact task phase transition physical clocks; derived initial-export phase assignment retained in history metadata.'
save('MOTION_BURDEN_AUDIT.json',m)
e=load(OUT/'NEURAL_Q_EVALUATION.json')
for lat in e['inference']:
 lat['resident_loaded_bundle_bytes']=lat.pop('parameter_and_normalization_bytes')
 path=FROZEN/'weights.npz' if lat['model']!='C_neural_challenger' else Path(load(OUT/'MODEL_AND_FEATURE_CONTRACT.json')['model'])
 with np.load(path) as w:
  names=['x_mean','x_scale','y_mean','y_scale']+(['linear_W','linear_b'] if lat['model']=='A_frozen_linear' else [f'Q_{a}{i}' for i in range(3) for a in ['W','b']])
  lat['scorer_required_array_bytes']=sum(w[k].nbytes for k in names)
e['test_baseline_comparison']={'new_minus_frozen_mean_regret_N_s':e['models']['C_neural_challenger']['test']['mean_selection_regret_N_s']-e['models']['A_frozen_linear']['test']['mean_selection_regret_N_s'],'observed_decision_advantage':'FAIL on exposed diagnostic test; no test-driven refitting','motion_tradeoff_improvement':'NOT_DEMONSTRATED','host_entry':'NOT_READY'}
save('NEURAL_Q_EVALUATION.json',e)
print('DERIVED_PHASE_AND_MEMORY_REFINED')
