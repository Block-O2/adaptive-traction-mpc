from pathlib import Path
import os,sys,json,time,hashlib,importlib.util,ast,itertools
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
sp=importlib.util.spec_from_file_location('raw_arithmetic',P/'control/independent_recompute.py');ar=importlib.util.module_from_spec(sp);sp.loader.exec_module(ar)
node=next(n for n in ast.parse((P/'control/base_campaign.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw');ns=dict(np=np,itertools=itertools,array_items=ar.array_items);exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen_exact_field_comparator','exec'),ns);compare=ns['compare_raw']
selection=read('FROZEN_SELECTION.json');assert selection['primary'] is not None;cid=selection['primary']['id'];protocol=read('NEW_PREFIX_VALIDATION_PROTOCOL.json')
assert sha(P/'FROZEN_SELECTION.json')==protocol['selection_sha256'];assert sha(P/'EXECUTION_CODE_MANIFEST.json')==protocol['execution_manifest_sha256'];assert sha(P/'SELECTION_RULE.json')==selection['selection_rule_sha256']
for rel,h in read('EXECUTION_CODE_MANIFEST.json')['files'].items():assert ar.sha(P/rel)==h
for g in ['repeat','W1','W2']:assert read(g+'_DONE.json')['all_children_joined']
cross=compare(P/'source/results'/selection['source_id'],P/'source/results'/('repeat_'+cid));assert cross['status']=='PASS';put('audit/CROSS_BATCH_REPEAT.json',cross)
for g in ['repeat','W1','W2']:assert read('audit/'+g+'_'+cid+'_repeat_REPEAT_GATE.json')['status']=='PASS'
rows=[];states=[]
def physical_state(ident,physical_s):
 tr=np.load(P/'source/results'/ident/'trace.npz');i=int(np.argmin(abs(tr['time_s']-physical_s)));assert abs(tr['time_s'][i]-physical_s)<1e-8
 return tr['evaluation_only_human_state_rad_rad_s'][i].tolist()
for g in ['W1','W2']:
 config=read(g+'_PLAN.json');result=read(g+'_RESULTS.json')['rows'];b=next(r for r in result if r['candidate']['id']=='B');t=next(r for r in result if r['candidate']['id']=='T');d=next(r for r in result if r['candidate']['id']==cid)
 # Check the exact frozen recipe, allowing only the deterministic-repeat name/tag.
 for c in config['arms']:
  if c['id'] not in [cid,cid+'_repeat']:continue
  v={k:x for k,x in c.items() if k not in ['id','repeat_of']};expected={k:x for k,x in selection['primary'].items() if k!='id'};assert v==expected
 # Full task values never compare absolute J_F between conditions.
 def variation(ident):
  z=np.load(P/'motion_series'/(ident+'.npz'));v=z['true_dq_rad_s'];a=z['acceleration_rad_s2'];j=z['jerk_rad_s3'];return dict(TV_v=float(np.linalg.norm(np.diff(v,axis=0),axis=1).sum()),TV_a=float(np.linalg.norm(np.diff(a,axis=0),axis=1).sum()),jerk_RMS=float(np.sqrt(np.mean(np.sum(j*j,axis=1)))))
 vt=variation(t['id']);vd=variation(d['id']);rel={k:vd[k]/vt[k]-1 for k in vt};dj=d['J_F_N_s']-t['J_F_N_s'];qualified=bool(d['motion']['acceptance_pass'] and d['absolute_safety'] and d['task']=='PASS' and d['receipt']=='PASS')
 signal=(dj<=-.5 and max(rel.values())<=.002) or (min(rel.values())<=-.005 and max(rel.values())<=.002 and dj<=.2)
 # T and D have exact common native body/contact/torque history until D first changes a reference.
 su=read('source/results/'+d['id']+'/summary.json');first=next(lr for lr in su['learning_records'] if 'second_round_posture' in lr['selected_plan']['execution_screen']);decision=su['decisions'][first['decision_index']];request=decision['decision_request_time_s'];splice=decision['activation_timestamp_s']+.04
 files=[P/'source/results'/ident/'runtime_artifacts.json.gz' for ident in [t['id'],d['id']]];n=0
 for arow,brow in zip(ar.array_items(files[0],'native_states_evaluation_only'),ar.array_items(files[1],'native_states_evaluation_only')):
  if arow['time_s']>splice+1e-9:break
  for k in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']:assert arow.get(k)==brow.get(k),(g,'PRE_INTERVENTION_NATIVE_DIFF',k,arow['time_s'])
  n+=1
 labels=read('output/'+d['id']+'_DECISIONS.json')['rows'];prefix_labels=[x for x in labels if x.get('legal_shared_prefix')];assert {x['phase'] for x in prefix_labels}=={'OUTBOUND','RETURN'}
 assert len(prefix_labels)==2
 branch=d['branch'];state=dict(condition=g,condition_spec=config['condition'],full_fork_hash=branch['full_hash'],native_fork_hash=branch['native_hash'],fork_physical_s=branch['physical_time_s'],fork_actual_human_evaluation_only=physical_state(d['id'],branch['physical_time_s']),first_posture_request_physical_s=request,first_posture_request_actual_human_evaluation_only=physical_state(d['id'],request),T_D_history_exact_before_first_splice=True,native_rows_before_splice_compared=n,legal_prefix_labels=prefix_labels,scope='Full live-state initial fork after OUTBOUND0. RETURN0 background policy executes later through native admission, identically for T and D until the first D intervention. Native truth used only for post-run evaluation.')
 states.append(state)
 rows.append(dict(condition=g,paired_B_J_F=b['J_F_N_s'],paired_T_J_F=t['J_F_N_s'],candidate_J_F=d['J_F_N_s'],delta_J_F_vs_T=dj,force_gain_vs_B_percent=d['motion']['gain_percent'],motion_change_vs_T=rel,original_qualification=qualified,original_motion_vs_B=d['motion'],task=d['task'],safety=d['absolute_safety'],receipt=d['receipt'],frozen_research_signal=bool(signal),validation_pass=bool(qualified and signal and d['motion']['gain_percent']>=1.),deterministic_repeat='PASS',phase_cost=d['phase_cost'],phase_durations=d['phase_durations']))
assert len({x['full_fork_hash'] for x in states})==2 and len({x['native_fork_hash'] for x in states})==2
assert np.max(abs(np.array(states[0]['fork_actual_human_evaluation_only'])-np.array(states[1]['fork_actual_human_evaluation_only'])))>1e-6
assert np.max(abs(np.array(states[0]['first_posture_request_actual_human_evaluation_only'])-np.array(states[1]['first_posture_request_actual_human_evaluation_only'])))>1e-6
put('audit/NEW_PREFIX_STATE_AND_HISTORY_AUDIT.json',dict(status='PASS',states=states,no_replayed_or_assigned_Human_state=True,near_intervention_states_different=True,controller_imported=False))
put('VALIDATION_RESULTS.json',dict(status='PASS' if all(r['validation_pass'] for r in rows) else 'FAIL_NO_RESELECTION',frozen_primary=selection['primary'],source_selection_sha256=sha(P/'FROZEN_SELECTION.json'),source_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST.json'),new_conditions=2,passed_conditions=sum(r['validation_pass'] for r in rows),deterministic_development_repeat='PASS',cross_batch_full_raw_repeat='PASS',rows=rows,evidence_level='PHYSICAL_LEVEL1 / SCIENTIFIC_SIMULATION',same_Human_only=True,cross_patient_generalization=False,selection_unchanged_after_validation=True,math_vs_physics='Offline certificates and min-jerk proof are separate from actual full task/native/receipt checks. Numerical independent audits are one-agent separate arithmetic, not a second human audit.'))
print(json.dumps(dict(status='PASS' if all(r['validation_pass'] for r in rows) else 'FAIL_NO_RESELECTION',rows=rows)),flush=True)
