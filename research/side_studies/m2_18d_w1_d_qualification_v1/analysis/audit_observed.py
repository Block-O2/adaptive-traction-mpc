from pathlib import Path
import sys,os,json,time,hashlib,importlib.util
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
A=P.parent/'m2_18d_t_second_round_coordination_v1'
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
sp=importlib.util.spec_from_file_location('independent_raw',P/'control/independent_recompute.py');raw=importlib.util.module_from_spec(sp);sp.loader.exec_module(raw)
frozen={n:sha(P/n)==sha(A/n) for n in ['FROZEN_18D.json','FROZEN_SELECTION.json','MOTION_ACCEPTANCE_PROTOCOL.json','SELECTION_RULE.json','control/round_planner.py','code/terminal_repair.py']};assert all(frozen.values())
rows=[]
for g in ['W1','R0','O0','W2']:
 if not (P/(g+'_RESULTS.json')).exists():continue
 pair=read(g+'_PAIR_GATE.json');assert pair['status']=='PASS' and pair['all_parent_unchanged'] and len(set(pair['hashes'].values()))==1
 assert read(g+'_PARENT_GATE.json')['status']=='PASS'
 for r in read(g+'_RESULTS.json')['rows']:
  ident=r['id'];su=read('source/results/'+ident+'/summary.json');receipts=list(raw.array_items(P/'source/results'/ident/'runtime_artifacts.json.gz','command_receipts'));pe=[];te=[]
  for lr in su['learning_records']:
   screen=lr['selected_plan']['execution_screen'];sc=lr['selected_plan']['schedule'];owned=[x for x in receipts if x.get('applied') and x.get('native_steps',0)>0 and lr['start_time_s']-1e-9<=x['start_physics_s']<lr['end_time_s']-1e-9]
   if 'terminal_duration_intervention' in screen:
    x=screen['terminal_duration_intervention'];co=x['terminal_contract'];ok=x['status']=='ACCEPTED' and co['factor']==1.5 and co['target_unchanged'] and co['pass_velocity_unchanged'] and abs(co['proposed_duration_s']-np.ceil(co['original_duration_s']*1.5/.005-1e-10)*.005)<1e-12
    te.append(dict(metadata=x,activated=lr['selected_plan_activated'],owned_native_steps=sum(x['native_steps'] for x in owned),identity_valid=bool(ok)))
   if 'second_round_posture' in screen:
    x=screen['second_round_posture'];ok=x['status']=='ACCEPTED' and x['outer_pass_velocity_unchanged'] and x['all_18D_parameters_unchanged'] and x['delta_deg']==[.3,-.3] and not x['truth_consumed'] and abs(sc['duration_s']-x['original_duration_s'])<1e-12 and np.max(abs(np.array(lr['selected_plan']['target_q_rad'])-np.array(x['proposed_target_rad'])))<1e-10
    pe.append(dict(metadata=x,decision_index=lr['decision_index'],activated=lr['selected_plan_activated'],owned_native_steps=sum(x['native_steps'] for x in owned),positive_receipts=len(owned),identity_valid=bool(ok)))
  identity=all(x['identity_valid'] and x['activated'] and x['owned_native_steps']>0 for x in pe+te) and len(pe)==len(r['candidate'].get('posture',[])) and (r['candidate']['base']!='T' or len(te)==1)
  rows.append(dict(id=ident,execution_identity_pass=identity,posture=pe,T=te,all_native_receipt_lineage_pass=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')['status']=='PASS',pair_full_state_hash=pair['hashes'][ident],receipt_binding='original source/version/request context and half-open active-plan interval, positive native step/torque ownership; direct plan_request_id is not present in every original receipt and is not synthesized'))
out=dict(status='PASS' if all(r['execution_identity_pass'] and r['all_native_receipt_lineage_pass'] for r in rows) else 'FAIL_CANDIDATE_EXECUTION_IDENTITY',unix=time.time(),frozen_byte_identity=frozen,rows=rows,truth_firewall='fixed preregistered intents; native truth used only by offline measurement; original deployable source unchanged',independence='separate raw arithmetic path in one agent, not independent person or second agent')
put('audit/INTERVENTION_EXECUTION_AUDIT.json',out)
print(json.dumps(dict(status=out['status'],rows=[dict(id=x['id'],identity=x['execution_identity_pass']) for x in rows])),flush=True)
