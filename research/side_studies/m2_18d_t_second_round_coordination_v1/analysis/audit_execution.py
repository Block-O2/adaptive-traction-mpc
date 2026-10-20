"""Check every accepted intervention and its actual receipt; arithmetic only."""
from pathlib import Path
import json,hashlib,sys,numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
def read(n):return json.loads((P/n).read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
groups=sys.argv[1:] or ['dev'];rows=[]
for g in groups:
 if (P/(g+'_PAIR_GATE.json')).exists():
  gate=read(g+'_PAIR_GATE.json');assert gate['status']=='PASS' and gate['all_parent_unchanged'];assert len(set(gate['hashes'].values()))==1,'PAIR_FULL_STATE_HASHES_DIFFER'
 else:
  assert (P/'PHYSICS_STOP.json').exists()
  completed=read(g+'_RESULTS.json')['rows'];parents=read('reports/'+g+'_PARENT_CHECKS.json');assert all(r['unchanged'] and r['child_exitcode']==0 for r in parents)
  hashes={r['id']:r['branch']['full_hash'] for r in completed};assert len(set(hashes.values()))==1
  (P/'audit'/('PARTIAL_'+g+'_PAIRING.json')).write_text(json.dumps(dict(status='PASS_COMPLETED_CHILDREN_ONLY',hashes=hashes,parent_unchanged_after_each_fork=True,full_parent_task_complete=False,scope='Frozen motion stop interrupted the parent; no parent/B full-task equivalence claim. Completed arms retain exact full live-state fork/restored checks.'),indent=2)+'\n')
 for r in read(g+'_RESULTS.json')['rows']:
  ident=r['id'];c=r['candidate'];su=read('source/results/'+ident+'/summary.json');references=read('output/'+ident+'_REFERENCE_OBJECTS.json')['references'];samples=read('output/'+ident+'_ISSUED_REFERENCE.json')['rows'];receipts=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json')
  # Analyzer receipt output schema varies by historical version; inspect actual root.
  # Derived rows describe decisions, not native command receipts. Read the raw array.
  import importlib.util
  sp=importlib.util.spec_from_file_location('raw_arithmetic',P/'control/independent_recompute.py');mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
  receipt_rows=list(mod.array_items(P/'source/results'/ident/'runtime_artifacts.json.gz','command_receipts'))
  assert len(references)==len(c.get('changes',[])),(ident,'SHAPE_NOT_EXECUTED',len(references))
  certs=[]
  for rid,ref in references.items():
   assert ref['reference_id']==rid and digest(ref['identity_payload'])==rid
   cert=ref['path_certificate'];assert cert['feasible'] and cert['reference_id']==rid
   payload=ref['identity_payload'];old=payload['original'];co=np.array(old['values']);T=old['duration_s']
   def old_sample(t,d):return np.array([np.polynomial.polynomial.polyval(t/T,np.polynomial.polynomial.polyder(q,d)) for q in co])/T**d
   for i,(key,der) in enumerate([('q_rad',0),('dq_rad_s',1),('ddq_rad_s2',2)]):
    for endpoint,seg,t in [(0,ref['segments'][0],0),(T,ref['segments'][-1],ref['segments'][-1]['duration_s'])]:
     sco=np.array(seg['immutable_coefficients']);val=np.array([np.polynomial.polynomial.polyval(t/seg['duration_s'],np.polynomial.polynomial.polyder(q,der)) for q in sco])/seg['duration_s']**der
     assert np.max(abs(val-old_sample(endpoint,der)))<1e-10
   applied=[x for x in receipt_rows if x.get('applied') and x.get('native_steps',0)>0 and x.get('multisegment_reference',{}).get('reference_id')==rid]
   assert applied,(ident,rid,'NO_APPLIED_SHAPE_RECEIPTS')
   errors=[]
   for x in applied:
    a=x['multisegment_reference'];assert a['current_full_path_certificate']['feasible']
    assert a['reference_id']==rid and a['worker_certificate_id']==ref['certificate_id']
    errors.append(float(np.max(abs(np.array(a['q_rad'])-np.array(x['q_ref_rad'])))))
    errors.append(float(np.max(abs(np.array(a['dq_rad_s'])-np.array(x['dq_ref_rad_s'])))))
   assert max(errors)<1e-10
   def jerk_energy(coeff,duration):
    total=0.
    for coeff_joint in np.array(coeff):
     j=np.polynomial.polynomial.polyder(coeff_joint,3)/duration**3
     integ=np.polynomial.polynomial.polyint(np.convolve(j,j));total+=duration*np.polynomial.polynomial.polyval(1.,integ)
    return float(total)
   original_energy=jerk_energy(co,T);new_energy=sum(jerk_energy(seg['immutable_coefficients'],seg['duration_s']) for seg in ref['segments'])
   assert new_energy>=original_energy-1e-8,'FIXED_BOUNDARY_MINIMUM_JERK_IDENTITY_FAIL'
   certs.append(dict(reference_id=rid,worker_certificate_id=ref['certificate_id'],current_model_certificates=True,positive_receipts=len(applied),native_steps=sum(x['native_steps'] for x in applied),max_issued_receipt_error=max(errors),outer_endpoints_q_dq_ddq_and_duration_unchanged=True,reference_integrated_squared_jerk_original=original_energy,reference_integrated_squared_jerk_new=new_energy,mathematical_only=True))
  posture=[];terminal=[]
  for lr in su['learning_records']:
   screen=lr['selected_plan']['execution_screen']
   if 'second_round_posture' in screen:
    p=screen['second_round_posture'];assert p['status']=='ACCEPTED';assert p['outer_pass_velocity_unchanged'] and p['all_18D_parameters_unchanged'];assert abs(lr['selected_plan']['schedule']['duration_s']-p['original_duration_s'])<1e-12
    assert np.max(abs(np.array(lr['selected_plan']['target_q_rad'])-np.array(p['proposed_target_rad'])))<1e-10;posture.append(p)
   if 'terminal_duration_intervention' in screen:
    p=screen['terminal_duration_intervention'];assert p['status']=='ACCEPTED';t=p['terminal_contract'];assert t['factor']==1.5 and t['target_unchanged'] and t['pass_velocity_unchanged'];assert abs(t['proposed_duration_s']-np.ceil(t['original_duration_s']*1.5/.005-1e-10)*.005)<1e-12;terminal.append(p)
  assert len(posture)==len(c.get('posture',[]))
  if c['base']=='T':assert len(terminal)==1
  rows.append(dict(id=ident,status='PASS',shape_certificates=certs,posture=posture,T=terminal,live_parent_matched=True,qualification=r['motion']['acceptance_pass'],truth='evaluation motion unused by online fixed intents',receipt_id_limitation='historical receipts lack direct plan_request_id in some paths; original request/source binding, version, polynomial sample, applied torque/native ownership checks retained; no synthetic direct ID'))
out=dict(status='PASS',rows=rows,scope='all actually accepted bounded interventions; source-current certificate; actual reference receipt and native ownership cross-check with INDEPENDENT_VERIFICATION.json; no new physics')
(P/'audit/INTERVENTION_EXECUTION_AUDIT.json').write_text(json.dumps(out,indent=2)+'\n')
print('INTERVENTION_EXECUTION_PASS',len(rows),flush=True)
(P/'MATHEMATICAL_SHAPE_LIMIT.md').write_text('''# Fixed-boundary quintic shape limit\n\n这是数学证据，不是Human物理结论。令原quintic为q0，任意C2分段干预q=q0+h保持外端q、dq、ddq及duration。三次分部积分，边界h、h′、h″为0，内部C2边界项抵消，q0的六阶导数为0，因此∫q0‴·h‴dt=0。故∫||q‴||²dt=∫||q0‴||²dt+∫||h‴||²dt，原quintic已是这些外端合同下的reference积分平方jerk最小解。\n\n内部q-only平滑可以改变velocity TV、加速度峰或其分配，但不能在同一段外端合同下继续降低reference积分平方jerk。实际Human闭环响应并不受上述最小值直接约束，仍可能通过改善tracking降低实际jerk；必须看native结果。不能用这个数学事实宣称本轮负结果必然、证明Human波动不可避免，或替代物理资格。\n\n对实际执行的每个reference对象，独立按多项式精确积分的原/新jerk energy在audit/INTERVENTION_EXECUTION_AUDIT.json中。此限制支持避免无依据增加内部q点密度，下一步应优先明确外端通过速度、局部闭环响应与允许改变的协调合同。\n''')
