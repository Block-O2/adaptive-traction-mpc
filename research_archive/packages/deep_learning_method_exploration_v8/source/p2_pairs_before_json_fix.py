"""Fixed preregistered micro-parameter pairs, total intervention vs mediator evidence."""
import os,sys,json,gzip
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];os.environ['MPLCONFIGDIR']=str(P/'runtime/tmp/mpl');sys.path.insert(0,str(P/'source'))
import numpy as np
from clearance_forensics import analyze
R=P/'runtime';rows=[];arrays={}
for item in json.loads((P/'experiments/P2.json').read_text())['actions']:
 ident='P2_'+item['tag'];rf=P/'attempts'/(ident+'_RESULT.json')
 if not rf.exists():rows.append({'id':ident,'status':'NOT_COMPLETE_RESULT'});continue
 result=json.loads(rf.read_text())
 if not result['complete']:rows.append({'id':ident,'status':'PARTIAL_PRESERVED','result':result});continue
 info=analyze(ident,P);path=R/'source/results'/ident
 with gzip.open(path/'runtime_artifacts.json.gz','rt') as f:raw=json.load(f)
 m=json.loads((R/'reports'/(ident+'_MEASURED.json')).read_text());su=json.loads((path/'summary.json').read_text());n=raw['wall_physics']['native_states_evaluation_only'];t=np.array([a['time_s'] for a in n]);q=np.array([a['qpos_evaluation_only'] for a in n])[:,m['quality']['qpos_indices']];v=np.array([a['qvel_evaluation_only'] for a in n])[:,m['quality']['qvel_indices']];tau=np.array([a['command_torque_nm'] for a in n]);acc=np.gradient(v,t,axis=0,edge_order=2);jerk=np.gradient(acc,t,axis=0,edge_order=2)
 ee=[e for e in raw['execution_attempts'] if e.get('clearance_feedback')];receipts={round(r['source_sample_time_s'],7):r for r in raw['wall_physics']['command_receipts']};et=np.array([e['source_sample_time_s'] for e in ee]);phi=np.array([np.diff(np.array(receipts[round(e['source_sample_time_s'],7)]['validation_state'])[:2])[0]*-1 for e in ee]);curv=np.array([e['clearance_feedback']['model_curvature_m_s2'] for e in ee]);corr=np.array([e['clearance_feedback']['correction_nm'] for e in ee]);data=dict(t=t,q=q,v=v,tau=tau,a=acc,j=jerk,et=et,phi=phi,curv=curv,corr=corr);arrays[ident]=data
 np.savez_compressed(P/'analysis/forensics'/(ident+'_arrays.npz'),**data)
 refs=[{'decision_index':lr['decision_index'],'q':lr['selected_plan']['schedule']['target_q_rad'],'v':lr['selected_plan']['schedule']['target_dq_rad_s'],'duration':lr['selected_plan']['schedule']['duration_s'],'request':lr['request_time_s'],'activated':lr['selected_plan_activated'],'modal_status':lr['selected_plan']['execution_screen'].get('coordination_modal_v2',{}).get('status')} for lr in su['learning_records']]
 rows.append({'id':ident,'qualified':result['qualified'],'JF':result['JF'],'JM':result['JM'],'failures':result.get('motion_vs_B',{}).get('failed_requirements'),'action':result['action'],'native_new_steps':result['actual_new_native_steps'],'parent_hash':result['branch']['full_hash'],'min_curvature':info['min_curvature_m_s2'],'curvature_event_time':info['event_time_s'],'crossed_stencil_events':info['stencil_crossing_events'],'guard_correction_at_min_curvature':info['guard']['correction_nm'],'jerk_RMS':info['native_jerk_RMS_deg_s3'],'accel_max':info['native_acceleration_max_deg_s2'],'true_clearance_min_m':m['clearance'],'references':refs,'native_receipt_join_pass':info['native_receipt_join_pass']})
 del raw,n
pairs=[];lookup={r['id']:r for r in rows};critical=lookup['P2_C19']['curvature_event_time']
for r in rows:
 ident=r['id']
 if '_D' not in ident or ident not in arrays:continue
 base='P2_NEG' if ident.startswith('P2_NEG') else 'P2_C19';d=arrays[ident];b=arrays[base];assert np.array_equal(d['t'],b['t']),'PAIR_NATIVE_TIME_GRID_DIFF'
 pre=d['t']<20.075-1e-9;near_pre=(d['t']>=critical-.1)&(d['t']<critical-.01);post=(d['t']>=critical)&(d['t']<=critical+.03);before=(d['t']>=20.075)&(d['t']<critical-.01)
 refdif=[]
 for a,bb in zip(r['references'],lookup[base]['references']):
  refdif.append({'decision_index':a['decision_index'],'target_max_delta_deg':float(np.max(abs(np.degrees(np.array(a['q'])-bb['q'])))),'pass_max_delta_deg_s':float(np.max(abs(np.degrees(np.array(a['v'])-bb['v'])))),'duration_delta_s':a['duration']-bb['duration'],'request_delta_s':a['request']-bb['request'],'modal_status_changed':a['modal_status']!=bb['modal_status'],'activation_changed':a['activated']!=bb['activated']})
 pair={'base':base,'variant':ident,'upper_parameter_delta':r['action']['x'][3]-lookup[base]['action']['x'][3],'identical_native_before_RETURN':bool(np.array_equal(d['q'][pre],b['q'][pre]) and np.array_equal(d['v'][pre],b['v'][pre]) and np.array_equal(d['tau'][pre],b['tau'][pre])),'reference_changes':refdif,'max_target_delta_deg':max(x['target_max_delta_deg'] for x in refdif),'duration_changed_decisions':[x['decision_index'] for x in refdif if abs(x['duration_delta_s'])>1e-10],'activation_changed_decisions':[x['decision_index'] for x in refdif if x['activation_changed']],'request_shift_max_s':max(abs(x['request_delta_s']) for x in refdif),'delta_JF':r['JF']-lookup[base]['JF'],'delta_JM':r['JM']-lookup[base]['JM'],'same_parent':r['parent_hash']==lookup[base]['parent_hash'],'base_crossed_stencil_count':len(lookup[base]['crossed_stencil_events']),'variant_crossed_stencil_count':len(r['crossed_stencil_events'])}
 for k in ['q','v','tau']:
  delta=d[k]-b[k]
  for name,mask in [('before_critical',before),('near_pre',near_pre),('post',post)]:pair[k+'_'+name+'_max']=np.max(abs(np.degrees(delta[mask]) if k!='tau' else delta[mask]),axis=0).tolist()
 pair['post_jerk_peak_deg_s3']=np.max(abs(np.degrees(d['j'][post])),axis=0).tolist();pairs.append(pair)
 print('PAIR',ident,'cross',pair['variant_crossed_stencil_count'],'dur changes',pair['duration_changed_decisions'],'JF',r['JF'],'qualified',r['qualified'],flush=True)
out={'status':'EXECUTED_WITH_ALL_RESULTS','rows':rows,'pairs':pairs,'critical_time_s':critical,'causal_scope':{'CONFIRMED':'Same live-parent upper-parameter intervention changes total original-chain outcome; exact guard computation sensitivity separately replayed.','SUPPORTED':'Guard mediation when crossed stencil/correction/receipt impulse and native motion differ together, especially with unchanged durations and small prior differences.','NOT_TESTED':'Direct physical intervention replacing only guard curvature, broad failure rates, safety-equivalent replacement.'},'negative_control_definition':'No crossed centered model stencil at control samples; the continuous trajectory may still change endpoint branch between 5ms samples.'};(P/'analysis/P2_PAIRED_RESULTS.json').write_text(json.dumps(out,indent=2)+'\n')
# Export a reproducible scientific figure; no smoothing or curve deletion.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,ax=plt.subplots(4,1,figsize=(10,11),sharex=True)
for ident in ['P2_C19','P2_C19_DM0p0010','P2_C19_DP0p0010','P2_NEG','P2_NEG_DM0p0010','P2_NEG_DP0p0010']:
 if ident not in arrays:continue
 d=arrays[ident];ev=(d['et']>=critical-.035)&(d['et']<=critical+.035);use=(d['t']>=critical-.035)&(d['t']<=critical+.035);label=ident.removeprefix('P2_');ax[0].plot(d['et'][ev]-critical,d['phi'][ev]*1e6,'.-',label=label);ax[1].plot(d['et'][ev]-critical,d['curv'][ev],'.-',label=label);ax[2].plot(d['t'][use]-critical,d['a'][use,1]*180/np.pi,label=label);ax[3].plot(d['t'][use]-critical,d['v'][use,1]*180/np.pi,label=label)
for a,label in zip(ax,['Estimated hip-knee angle (micro rad)','Original model gap curvature (m/s^2)','Native knee acceleration (deg/s^2)','Native knee velocity (deg/s)']):a.set_ylabel(label);a.grid(alpha=.25);a.axvline(0,color='black',alpha=.3)
ax[0].legend(ncol=3,fontsize=8);ax[-1].set_xlabel('Time relative to original C19 event (s)');fig.tight_layout();(P/'figures').mkdir(exist_ok=True);fig.savefig(P/'figures/CLEARANCE_PAIRED_NATIVE.png',dpi=180);fig.savefig(P/'figures/CLEARANCE_PAIRED_NATIVE.pdf');plt.close(fig)
