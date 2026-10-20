"""Independent logged intent-to-actual linkage. No physics/controller imports."""
from pathlib import Path
import os,json,sys,time,ast,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
out=[]
for g in ['reproduction','N2','development','U1','U2','U3']:
 if not (P/(g+'_DONE.json')).exists():continue
 context=read('audit/'+g+'_FORK_CONTEXT.json');fork=context['physical_s'];base=P/'source/results'/(g+'_B')/'trace.npz'
 for r in read(g+'_RESULTS.json')['rows']:
  arm=r['arm'];ident=r['id'];folder=P/'source/results'/ident;expected=None if arm=='B' else read('FROZEN_18D.json' if arm=='E' else 'CANDIDATE.json' if arm.startswith('C') else 'BOUNDED_REPAIR.json')['free_parameters']
  su=json.loads((folder/'summary.json').read_text());receipt=read('reports/'+ident+'_EXECUTED_RESIDUAL_RECEIPTS.json');by={x['decision_index']:x for x in receipt['rows']};details=[]
  for lr in su['learning_records']:
   meta=lr.get('selected_plan',{}).get('execution_screen',{}).get('free_trajectory')
   if not meta:continue
   assert expected is not None and meta['parameters']==expected,(ident,meta)
   if 'original_target' not in meta:
    assert meta['status']=='REJECTED' and meta['reason']=='NORMALIZED_TARGET_OUT_OF_RANGE'
    details.append(dict(decision_index=lr['decision_index'],accepted=False,physically_executed=False,rejection_reason=meta['reason']));continue
   owned=by[lr['decision_index']];ph=owned['phase'];j,k=(0,10) if ph=='OUTBOUND' else (5,14);start=np.deg2rad([5.,10.]);span=np.deg2rad([115.,110.])
   if ph=='RETURN':start,span=start+span,-span
   original=np.asarray(meta['original_target']);m=float(np.mean((original-start)/span));u=2*m-1;e=np.sin(np.pi*np.clip(m,0,1))**2;x=np.asarray(expected)
   c=e*(x[j]+x[k]*u+x[k+1]*u*u);d=e*(x[j+1]+x[j+2]*u+x[k+2]*u*u)
   assert abs(c-meta['common_shift'])<1e-14 and abs(d-meta['differential_shift'])<1e-14
   proposal=original+span*np.array([c+d,c-d]);assert np.max(abs(proposal-meta['proposed_target']))<1e-14
   details.append(dict(decision_index=lr['decision_index'],phase=ph,accepted=meta['status']=='ACCEPTED',activated=bool(lr.get('selected_plan_activated')),actual_native_steps=owned['actual_native_steps'],positive_receipts=len(owned['actual_command_receipts']),first_execution_physics_s=owned['first_execution_physics_s'],physically_executed=meta['status']=='ACCEPTED' and bool(lr.get('selected_plan_activated')) and owned['actual_native_steps']>0,common_shift=c,differential_shift=d))
  if expected is not None:assert details and any(x['physically_executed'] for x in details)
  fields={}
  with np.load(base) as b,np.load(folder/'trace.npz') as a:
   for key in a.files:
    if key in ['task_beta','task_residual_weights_nm']:
     ia=a['time_s'][a['stage']=='TASK']<=fork+1e-9;ib=b['time_s'][b['stage']=='TASK']<=fork+1e-9
    else:ia=a['time_s']<=fork+1e-9;ib=b['time_s']<=fork+1e-9
    x,y=a[key][ia],b[key][ib];fields[key]=bool(x.shape==y.shape and (np.array_equal(x,y,equal_nan=True) if x.dtype.kind in 'fc' else np.array_equal(x,y)))
   assert all(fields.values()),(ident,'PREFIX_MISMATCH')
  out.append(dict(id=ident,status='PASS',all_parameters_exact=True,independent_position_formula_verified=True,physically_executed_free_intents=sum(x['physically_executed'] for x in details),details=details,prefix_trace_exact=fields))
# New campaign contains no direct Human state assignment or physics stepping.
tree=ast.parse((P/'control/campaign.py').read_text());forbidden=[]
for n in ast.walk(tree):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['mj_step','mj_step1','mj_step2','reset']:forbidden.append(n.lineno)
 if isinstance(n,(ast.Assign,ast.AugAssign,ast.AnnAssign)):
  targets=n.targets if isinstance(n,ast.Assign) else [n.target]
  for target in targets:
   for z in ast.walk(target):
    if isinstance(z,ast.Attribute) and z.attr in ['qpos','qvel']:forbidden.append(n.lineno)
assert not forbidden,forbidden
put('audit/INTENT_TO_ACTUAL_EXECUTION.json',dict(status='PASS',unix=time.time(),rows=out,all_inherited_prefixes_exact=True,no_direct_state_assignment_in_new_campaign=True,claim='Logged accepted intent is joined through original positive-step receipts to actual native execution; reference and actual Human motion remain separate evidence. No future safety invariance or host real-time qualification inferred.',new_physics=0))
print('INTENT_EXECUTION_PASS',len(out))
