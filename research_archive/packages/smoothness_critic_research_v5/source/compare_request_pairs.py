from pathlib import Path
import os,sys,json
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'));from acl2_shared import put
import numpy as np
bs={f.stem:json.loads(f.read_text()) for f in (P/'analysis/branches').glob('*.json')};pairs=[]
for ident in bs:
 base='DEV_C19' if ident.startswith('DEV_LOCAL_') else 'DEV_BEST' if ident.startswith('FACT_BEST_') else 'DEV_C19' if ident.startswith('FACT_C19_') else None
 if not base or base not in bs:continue
 aa=bs[base]['issued_reference_decisions'];bb=bs[ident]['issued_reference_decisions'];r=dict(base=base,variant=ident,request_count_base=len(aa),request_count_variant=len(bb),matched_by='decision index, recording count mismatch explicitly',duration_changed_decisions=[],activation_changed_decisions=[],modal_acceptance_changed_decisions=[],max_request_time_shift_s=0.,max_selected_target_difference_deg=0.,actual_native_motion_comparison='analysis/RESULT_SUMMARY.json')
 for a,b in zip(aa,bb):
  r['max_request_time_shift_s']=max(r['max_request_time_shift_s'],abs(a['request_time_s']-b['request_time_s']))
  if a['duration_s']!=b['duration_s']:r['duration_changed_decisions'].append(a['decision_index'])
  if a['activated']!=b['activated']:r['activation_changed_decisions'].append(a['decision_index'])
  if a['accepted_modal']!=b['accepted_modal']:r['modal_acceptance_changed_decisions'].append(a['decision_index'])
  if a['target_q_rad'] is not None and b['target_q_rad'] is not None:r['max_selected_target_difference_deg']=max(r['max_selected_target_difference_deg'],float(np.max(abs(np.degrees(np.array(a['target_q_rad'])-np.array(b['target_q_rad']))))))
 with np.load(P/'runtime/motion_series'/(base+'.npz')) as a,np.load(P/'runtime/motion_series'/(ident+'.npz')) as b:
  t=np.intersect1d(np.round(a['time_s'],8),np.round(b['time_s'],8));ia=np.searchsorted(np.round(a['time_s'],8),t);ib=np.searchsorted(np.round(b['time_s'],8),t);pre=(a['phase'][ia]!='RETURN')&(b['phase'][ib]!='RETURN');r['before_RETURN_q_dq_exact_equal']=bool(np.array_equal(a['true_q_rad'][ia[pre]],b['true_q_rad'][ib[pre]]) and np.array_equal(a['true_dq_rad_s'][ia[pre]],b['true_dq_rad_s'][ib[pre]]));r['same_task_native_time_array']=bool(np.array_equal(a['time_s'],b['time_s']))
 pairs.append(r)
put('analysis/CAUSAL_REQUEST_PAIR_COMPARISON.json',dict(status='EXECUTED',pairs=pairs,scope='Same live causal parent within each job. Cross-job DEV/FACT share verified nominal cold commissioning and fork prefix; exact control identity audited separately. Feedback-dependent request/activation/reference changes after intervention are retained.'))
print('PAIRS',len(pairs));print([(r['variant'],r['max_request_time_shift_s'],r['duration_changed_decisions']) for r in pairs])
