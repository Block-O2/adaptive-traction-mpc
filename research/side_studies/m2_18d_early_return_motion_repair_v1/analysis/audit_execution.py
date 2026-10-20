from pathlib import Path
import sys,json,time,hashlib,importlib.util
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
A=P.parent/'m2_18d_w1_d_qualification_v1'
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
sp=importlib.util.spec_from_file_location('independent_raw',P/'control/independent_recompute.py');raw=importlib.util.module_from_spec(sp);sp.loader.exec_module(raw)
frozen={n:sha(P/n)==sha(A/n) for n in ['FROZEN_18D.json','FROZEN_SELECTION.json','MOTION_ACCEPTANCE_PROTOCOL.json','SELECTION_RULE.json','control/round_planner.py','code/terminal_repair.py']};assert all(frozen.values())
rows=[]
for g in read('EXPERIMENT_RESULTS.json')['groups']:
 pair=read(g+'_PAIR_GATE.json');assert pair['status']=='PASS' and pair['all_parent_unchanged'] and len(set(pair['hashes'].values()))==1
 assert read(g+'_PARENT_GATE.json')['status']=='PASS'
 for r in read(g+'_RESULTS.json')['rows']:
  ident=r['id'];su=read('source/results/'+ident+'/summary.json');receipts=list(raw.array_items(P/'source/results'/ident/'runtime_artifacts.json.gz','command_receipts'));pe=[];te=[];ee=[]
  for lr in su['learning_records']:
   screen=lr['selected_plan']['execution_screen'];sc=lr['selected_plan']['schedule'];d=su['decisions'][lr['decision_index']];owned=[x for x in receipts if x.get('applied') and x.get('native_steps',0)>0 and lr['start_time_s']-1e-9<=x['start_physics_s']<lr['end_time_s']-1e-9]
   def record(x,ok):return dict(metadata=x,decision_index=lr['decision_index'],request_id=d['timing_request_id'],activated=lr['selected_plan_activated'],owned_native_steps=sum(x['native_steps'] for x in owned),positive_receipts=len(owned),identity_valid=bool(ok),activation_outcome=d.get('activation_outcome'),continuity=d.get('reference_boundary_continuity'),rolling_composite=d.get('rolling_composite'))
   if 'terminal_duration_intervention' in screen:
    x=screen['terminal_duration_intervention'];co=x['terminal_contract'];ok=x['status']=='ACCEPTED' and co['factor']==1.5 and co['target_unchanged'] and co['pass_velocity_unchanged'] and abs(co['proposed_duration_s']-np.ceil(co['original_duration_s']*1.5/.005-1e-10)*.005)<1e-12;te.append(record(x,ok))
   if 'second_round_posture' in screen:
    x=screen['second_round_posture'];ok=x['status']=='ACCEPTED' and x['outer_pass_velocity_unchanged'] and x['all_18D_parameters_unchanged'] and x['delta_deg']==[.3,-.3] and not x['truth_consumed'] and abs(sc['duration_s']-x['original_duration_s'])<1e-12 and np.max(abs(np.array(lr['selected_plan']['target_q_rad'])-np.array(x['proposed_target_rad'])))<1e-10;pe.append(record(x,ok))
   if 'early_return_duration' in screen:
    x=screen['early_return_duration'];expected=next(v for v in r['candidate']['early'] if v['slot']==x['slot']);ok=x['status']=='ACCEPTED' and x['duration_factor']==expected['duration_factor'] and x['all_18D_parameters_unchanged'] and x['T_suffix_rule_unchanged'] and x['D_posture_rule_unchanged'] and x['fresh_fixed_duration_contract'] and not x['truth_consumed'] and abs(sc['duration_s']-np.ceil(x['original_duration_s']*x['duration_factor']/.005-1e-10)*.005)<1e-12 and np.max(abs(np.array(sc['target_q_rad'])-np.array(x['original_target_rad'])))<1e-10 and np.max(abs(np.array(sc['target_dq_rad_s'])-np.array(x['unchanged_pass_velocity_rad_s'])))<1e-10
    # Separate boundary-polynomial reconstruction checks actual receipt-issued references.
    T=sc['duration_s'];q0=np.array(sc['start_q_rad']);v0=np.array(sc['start_dq_rad_s']);q1=np.array(sc['target_q_rad']);v1=np.array(sc['target_dq_rad_s']);delta=q1-q0;co=np.stack([q0,T*v0,np.zeros(2),10*delta-T*(6*v0+4*v1),-15*delta+T*(8*v0+7*v1),6*delta-3*T*(v0+v1)],axis=1);u=np.linspace(0,1,int(round(T/.005))+1);qref=np.array([np.polynomial.polynomial.polyval(u,c) for c in co]).T;vref=np.array([np.polynomial.polynomial.polyval(u,np.polynomial.polynomial.polyder(c)) for c in co]).T/T
    from scipy.spatial import cKDTree
    tree=cKDTree(np.c_[qref,vref]);splice=lr['start_time_s']+d.get('rolling_composite',{}).get('splice_elapsed_s',0.);issued=[np.r_[a['q_ref_rad'],a['dq_ref_rad_s']] for a in owned if a['start_physics_s']>=splice-1e-9 and a['start_physics_s']<splice+T-1e-9];err=float(np.max(tree.query(np.array(issued))[0])) if issued else None;ok=bool(ok and err is not None and err<1e-8)
    er=record(x,ok);er.update(issued_reference_grid_max_error=err,issued_reference_positive_receipts=len(issued),fresh_certificate=sc['continuous_clearance_certificate']);ee.append(er)
  identity=all(x['identity_valid'] and x['activated'] and x['owned_native_steps']>0 for x in pe+te+ee) and len(pe)==len(r['candidate'].get('posture',[])) and len(ee)==len(r['candidate'].get('early',[])) and (r['candidate']['base']!='T' or len(te)==1)
  rows.append(dict(id=ident,execution_identity_pass=identity,posture=pe,T=te,early=ee,all_native_receipt_lineage_pass=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')['status']=='PASS',pair_full_state_hash=pair['hashes'][ident],receipt_binding='original scientific source/version/request + positive step ownership over half-open active plan intervals; absent direct receipt plan_request_id not synthesized'))
out=dict(status='PASS' if all(r['execution_identity_pass'] and r['all_native_receipt_lineage_pass'] for r in rows) else 'FAIL',unix=time.time(),frozen_byte_identity=frozen,rows=rows,truth_firewall='no native truth consumed by isolated intents; truth only offline evaluation',evidence_level='PHYSICAL_LEVEL1 SCIENTIFIC_SIMULATION; no host realtime qualification')
put('audit/INTERVENTION_EXECUTION_AUDIT.json',out);assert out['status']=='PASS';print('EXECUTION_IDENTITY_PASS',len(rows),flush=True)
