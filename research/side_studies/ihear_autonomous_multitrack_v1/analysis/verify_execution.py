from pathlib import Path
import os,sys,json,ast,time,hashlib,importlib.util,itertools,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name;A=P.parent/'m2_18d_early_return_motion_repair_v1'
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
sp=importlib.util.spec_from_file_location('independent_raw',P/'control/independent_recompute.py');raw=importlib.util.module_from_spec(sp);sp.loader.exec_module(raw)
array_items=raw.array_items
src=(P/'control/base_campaign.py').read_text();tree=ast.parse(src);exec(ast.get_source_segment(src,next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='compare_raw')))
frozen={n:sha(P/n)==sha(A/n) for n in ['FROZEN_18D.json','FROZEN_SELECTION.json','MOTION_ACCEPTANCE_PROTOCOL.json','SELECTION_RULE.json','control/round_planner.py','control/early_return_planner.py','code/terminal_repair.py']};assert all(frozen.values())
rebase=read('audit/PATH_REBASE.json')['path_only'];bad=[];count=0
for folder in ['source','code','deps','weights']:
 for old in (A/folder).rglob('*'):
  if not old.is_file() or 'results' in old.parts or '__pycache__' in old.parts or old.suffix=='.pyc':continue
  rel=str(old.relative_to(A));new=P/rel;count+=1;expected=old.read_text().replace(str(A),str(P)).encode() if rel in rebase else old.read_bytes()
  if not new.exists() or new.read_bytes()!=expected:bad.append(rel)
assert not bad,bad
newsrc=(P/'control/terminal_approach_planner.py').read_text();nt=ast.parse(newsrc)
assert not any(isinstance(n,ast.Attribute) and n.attr in ['qpos','qvel','gain','torque_limit'] for n in ast.walk(nt))
put('audit/SOURCE_CLOSURE_VERIFIED.json',dict(status='PASS',files=count,path_rebased_files=rebase,errors=bad,frozen_byte_identity=frozen,scope='Original source/code/deps/weights path-only copied; original B/plant/admission/safety unchanged. New bounded wrapper reads deployable/reference state only; keyword checks supplemented by manual call-path review.'))
results=read('EXPERIMENT_RESULTS.json');rows=[];native_effects=[]
for group in results['groups']:
 pair=read(group+'_PAIR_GATE.json');assert pair['status']=='PASS' and pair['all_parent_unchanged'] and len(set(pair['hashes'].values()))==1
 assert read(group+'_PARENT_GATE.json')['status']=='PASS'
 if group=='Bmap':
  for arm in ['B','T','D']:
   gate=compare_raw(P/'source/results'/(group+'_'+arm),P.parent/'m2_18d_w1_d_qualification_v1/source/results'/('R0_'+arm));put('audit/'+group+'_'+arm+'_R0_REPRODUCTION.json',gate);assert gate['status']=='PASS'
 for r in read(group+'_RESULTS.json')['rows']:
  ident=r['id'];su=read('source/results/'+ident+'/summary.json');receipts=list(array_items(P/'source/results'/ident/'runtime_artifacts.json.gz','command_receipts'));checks=[]
  for lr in su['learning_records']:
   screen=lr['selected_plan']['execution_screen'];sc=lr['selected_plan']['schedule'];d=su['decisions'][lr['decision_index']];owned=[a for a in receipts if a.get('applied') and a.get('native_steps',0)>0 and lr['start_time_s']-1e-9<=a['start_physics_s']<lr['end_time_s']-1e-9]
   intervention_keys=[key for key in ['terminal_duration_intervention','second_round_posture','early_return_duration','terminal_approach_velocity'] if key in screen]
   for key in intervention_keys:
    x=screen[key];ok=x['status']=='ACCEPTED'
    if key=='terminal_duration_intervention':
     co=x['terminal_contract'];ok=ok and co['factor']==1.5 and co['target_unchanged'] and co['pass_velocity_unchanged'] and abs(co['proposed_duration_s']-np.ceil(co['original_duration_s']*1.5/.005-1e-10)*.005)<1e-12
    if key=='second_round_posture':ok=ok and x['delta_deg']==[.3,-.3] and x['all_18D_parameters_unchanged'] and not x['truth_consumed'] and abs(sc['duration_s']-x['original_duration_s'])<1e-12 and np.max(abs(np.array(sc['target_q_rad'])-x['proposed_target_rad']))<1e-10
    if key=='early_return_duration':
     expected=next(v for v in r['candidate']['early'] if v['slot']==x['slot']);ok=ok and x['duration_factor']==expected['duration_factor'] and not x['truth_consumed'] and abs(sc['duration_s']-np.ceil(x['original_duration_s']*x['duration_factor']/.005-1e-10)*.005)<1e-12 and np.max(abs(np.array(sc['target_q_rad'])-x['original_target_rad']))<1e-10 and np.max(abs(np.array(sc['target_dq_rad_s'])-x['unchanged_pass_velocity_rad_s']))<1e-10
    if key=='terminal_approach_velocity':
     expected=r['candidate']['approach'][0];oldv=np.array(x['old_pass_velocity_rad_s']);newv=oldv.copy();newv[1]*=expected['knee_velocity_factor'];ok=ok and x['slot']==3 and x['knee_velocity_factor']==expected['knee_velocity_factor'] and not x['truth_consumed'] and abs(sc['duration_s']-x['unchanged_selected_duration_s'])<1e-12 and np.max(abs(np.array(sc['target_q_rad'])-x['unchanged_target_rad']))<1e-10 and np.max(abs(np.array(sc['target_dq_rad_s'])-newv))<1e-10
    # Reconstruct final executed quintic rather than trusting intervention metadata.
    T=sc['duration_s'];q0=np.array(sc['start_q_rad']);v0=np.array(sc['start_dq_rad_s']);q1=np.array(sc['target_q_rad']);v1=np.array(sc['target_dq_rad_s']);delta=q1-q0
    co=np.stack([q0,T*v0,np.zeros(2),10*delta-T*(6*v0+4*v1),-15*delta+T*(8*v0+7*v1),6*delta-3*T*(v0+v1)],axis=1);u=np.linspace(0,1,int(round(T/.005))+1);qref=np.array([np.polynomial.polynomial.polyval(u,c) for c in co]).T;vref=np.array([np.polynomial.polynomial.polyval(u,np.polynomial.polynomial.polyder(c)) for c in co]).T/T
    tree=cKDTree(np.c_[qref,vref]);splice=lr['start_time_s']+(d.get('rolling_composite') or {}).get('splice_elapsed_s',0.);issued=[np.r_[a['q_ref_rad'],a['dq_ref_rad_s']] for a in owned if a['start_physics_s']>=splice-1e-9 and a['start_physics_s']<splice+T-1e-9];err=float(np.max(tree.query(np.array(issued))[0])) if issued else None
    checks.append(dict(type=key,decision_index=lr['decision_index'],request_id=d['timing_request_id'],identity_pass=bool(ok and lr['selected_plan_activated'] and len(owned)>0 and err is not None and err<1e-8),positive_receipts=len(owned),native_steps=sum(a['native_steps'] for a in owned),issued_reference_max_grid_error=err,certificate=sc['continuous_clearance_certificate'],metadata_scope='D posture receipt describes parent selection before additional R3 velocity intent; final velocity independently checked by terminal_approach_velocity and polynomial receipts' if 'terminal_approach_velocity' in screen else 'final selected curve'))
  expected_counts={'second_round_posture':len(r['candidate'].get('posture',[])),'early_return_duration':len(r['candidate'].get('early',[])),'terminal_approach_velocity':len(r['candidate'].get('approach',[])),'terminal_duration_intervention':int(r['candidate']['base']=='T')}
  ok=all(c['identity_pass'] for c in checks) and all(sum(c['type']==k for c in checks)==v for k,v in expected_counts.items());assert ok,ident
  rows.append(dict(id=ident,status='PASS',interventions=checks,expected_counts=expected_counts,all_native_receipt_lineage=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')['status'],full_fork_hash=pair['hashes'][ident]))
  if r['candidate'].get('approach') or r['candidate'].get('early'):
   rz=next(x for x in results['rows'] if x['id']==ident);cut=rz['causal_response']['first_intervention_splice_task_s'];origin=float(np.load(P/'source/results'/ident/'trace.npz')['time_s'][np.load(P/'source/results'/ident/'trace.npz')['stage']=='TASK'][0]);n=0;err=[]
   parent_id=group+('_ER' if r['candidate'].get('approach') else '_D')
   left=array_items(P/'source/results'/ident/'runtime_artifacts.json.gz','native_states_evaluation_only');right=array_items(P/'source/results'/parent_id/'runtime_artifacts.json.gz','native_states_evaluation_only')
   for a,b in zip(left,right):
    if a['time_s']>=origin+cut-1e-9:break
    n+=1
    for k in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']:
     if a.get(k)!=b.get(k):err.append(k)
   assert not err,(ident,err)
   native_effects.append(dict(id=ident,parent=parent_id,pre_splice_native_rows=n,all_body_state_torque_contact_ownership_exact=True,actual_q_dq_response=rz['causal_response']))
put('audit/INTERVENTION_EXECUTION_AUDIT.json',dict(status='PASS',rows=rows,frozen_byte_identity=frozen,receipt_binding='original request/source/version plus activated half-open intervals, final reference and exact torque/native counts; missing direct plan_request_id never fabricated'))
put('derived/CAUSAL_RESPONSE_AUDIT.json',dict(status='PASS',checks=native_effects,conclusion='Before first new velocity splice all archived native body/command/contact/ownership fields equal ER; differences afterwards are actual physical effects of full causal intervention, not isolated mediation.'))
background=[]
if all(g in results['groups'] for g in ['Adev','Bmap']):
 for arm in ['B','T','D','ER']:
  la='Adev_'+arm;lb='Bmap_'+arm;sa=read('source/results/'+la+'/summary.json');cut=next(t['time_s'] for t in sa['task']['phase_transitions'] if t['to']=='RETURN');n=0;err=[]
  for a,b in zip(array_items(P/'source/results'/la/'runtime_artifacts.json.gz','native_states_evaluation_only'),array_items(P/'source/results'/lb/'runtime_artifacts.json.gz','native_states_evaluation_only')):
   if a['time_s']>=cut-1e-9:break
   n+=1
   for k in ['time_s','qpos_evaluation_only','qvel_evaluation_only','command_torque_nm','contact_pairs_evaluation_only','command_id','native_step_index']:
    if a.get(k)!=b.get(k):err.append(k)
  assert not err,(arm,err)
  za=np.load(P/'motion_series'/(la+'.npz'));zb=np.load(P/'motion_series'/(lb+'.npz'));ix=za['phase']=='RETURN'
  background.append(dict(arm=arm,pre_RETURN_native_rows=n,pre_RETURN_native_exact=True,RETURN_actual_q_max_delta_deg=np.rad2deg(np.max(abs(za['true_q_rad'][ix]-zb['true_q_rad'][ix]),axis=0)).tolist(),interpretation='Controlled removal of RETURN0 background with identical physical prior history. Cold-parent full address-space hashes are not claimed identical; shared history is not independent state coverage.'))
put('audit/BACKGROUND_CONTROL_AUDIT.json',dict(status='PASS',rows=background))
ledger=[]
for r in results['rows']:
 group=next(g for g in results['groups'] if r['id'].startswith(g+'_'));gp=read(group+'_PLAN.json');c=r['candidate'];new=bool(c.get('approach'))
 ledger.append(dict(run_id=r['id'],candidate_identity=c['id'],scientific_identity='ER110_R4_120 plus RETURN3 knee velocity factor '+str(c['approach'][0]['knee_velocity_factor']) if new else 'ER is display alias of frozen ER110_R4_120; no parameter change' if c['id']=='ER' else 'original matched '+c['id'],role='new development candidate' if new else 'frozen historical method / matched control',parent_baseline='ER110_R4_120' if new else 'historical B/18D/T/D lineage',parameters=c,state_background=gp['condition'],state_exposure='EXPOSED_W1_DEVELOPMENT' if group=='Adev' else 'EXPOSED_R0_DIAGNOSTIC',full_live_fork_hash=r['branch']['full_hash'],execution_manifest_sha256=sha(P/'EXECUTION_CODE_MANIFEST.json'),prephysics_protocol='INTERVENTION_PROTOCOL.md' if group=='Adev' else 'TRACK_B_PROTOCOL.json',prephysics_group_plan_sha256=sha(P/(group+'_PLAN.json')),math_result='audit/TRACK_A_PRECHECKS.json' if new else 'original frozen certificates plus live revalidation',native_result=r['metrics_path'],full_qualification=r['all_original_qualifications'],failure_items=r['motion']['failed_requirements'],actual_intervention_accepted=r['intervention_executed'],research_value='bounded causal response with failed excursion, no force ranking' if new else 'matched control or state applicability evidence'))
put('CANDIDATE_LEDGER.json',dict(status='COMPLETE',rows=ledger))
assert not any(n in sys.modules for n in ['mujoco','study_common','campaign','sac_env'])
for n in ['audit/SOURCE_CLOSURE_VERIFIED.json','audit/INTERVENTION_EXECUTION_AUDIT.json','derived/CAUSAL_RESPONSE_AUDIT.json','audit/BACKGROUND_CONTROL_AUDIT.json','CANDIDATE_LEDGER.json']:
 dst=R/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(P/n,dst)
print(json.dumps(dict(status='PASS',source_files=count,verified_runs=len(rows),native_effects=native_effects)),flush=True)
