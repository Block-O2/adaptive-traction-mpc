"""Read-only source, protocol, fork and action-permission audit; no physics."""
from pathlib import Path
import os,sys,json,hashlib,time,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5');O=P.parent/'constraint_geometry_learning_v4'
def sha(f):return hashlib.sha256(Path(f).read_bytes()).hexdigest()
def put(n,d):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
source_rows=[];bad=[]
for f in sorted((P/'jobs').glob('*/SOURCE_MANIFEST.json')):
 d=json.loads(f.read_text());mismatch=[r for r,h in d['files'].items() if not (P/r).is_file() or sha(P/r)!=h];cfg=P/'experiments'/(f.parent.name+'.json')
 if cfg.exists() and sha(cfg)!=d['config_sha256']:mismatch.append(str(cfg.relative_to(P)))
 done=P/'jobs'/f.parent.name/'WORKER_DONE.json';worker=json.loads(done.read_text()) if done.exists() else {};parent=worker.get('parent_checks',[])
 if any(not r['unchanged'] for r in parent):mismatch.append('PARENT_MUTATED')
 source_rows.append(dict(group=f.parent.name,files=len(d['files']),mismatches=mismatch,completed=done.exists(),parent_checks=len(parent),all_recorded_parents_unchanged=all(r['unchanged'] for r in parent)))
 bad.extend([f.parent.name+':'+r for r in mismatch])
# Entire copied mechanics/control closure admits only the documented root relocation.
relocation=[];closure_count=0
for folder in ['runtime/source','runtime/code','runtime/control','runtime/deps']:
 for f in (O/folder).rglob('*'):
  rel=f.relative_to(O/folder)
  if not f.is_file() or 'results' in rel.parts or '__pycache__' in rel.parts or '.git' in rel.parts:continue
  other=P/folder/rel
  if not other.is_file():relocation.append(str(other.relative_to(P))+':MISSING');continue
  old=f.read_bytes();new=other.read_bytes();expected=old
  try:
   text=old.decode();text=text.replace(str(O),str(P)).replace(str(P.parent/'representation_execution_v3'),str(P)).replace(str(P.parent/'autonomous_coordination_learning_v2'),str(P));expected=text.encode()
  except UnicodeDecodeError:pass
  closure_count+=1
  if new!=expected:relocation.append(str(other.relative_to(P)))
bad.extend(['UNEXPECTED_CLOSURE_CHANGE:'+r for r in relocation])
guard_rel='runtime/source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/clearance_feedback.py'
guard=dict(original_sha256=sha(O/guard_rel),executed_sha256=sha(P/guard_rel));guard['exact_equal']=guard['original_sha256']==guard['executed_sha256']
protocol={n:sha(P/'runtime'/n)==sha(O/'runtime'/n) for n in ['MOTION_ACCEPTANCE_PROTOCOL.json','FROZEN_18D.json','PARAMETER_MAP.json','ACTION_SET.json']};assert all(protocol.values()) and guard['exact_equal'],'ORIGINAL_GUARD_OR_CONTRACT_CHANGED'
excluded=set(json.loads((P/'audit/ACTION_PERMISSION_REVIEW.json').read_text())['excluded_from_formal_same_domain_comparison']);permission=[]
for f in sorted((P/'attempts').glob('*_RESULT.json')):
 r=json.loads(f.read_text());action=r['action'];ident=r['id'];errors=[]
 if action.get('family') in ['modal8','modal8_retimed']:
  x=np.asarray(action['x']);legacy=np.asarray(action.get('legacy',[0,0]));
  if x.shape!=(8,) or not np.all(abs(x)<=1+1e-12) or not np.all(abs(legacy)<=1+1e-12):errors.append('REGISTERED_PARAMETER_BOX')
  summary=P/'runtime/source/results'/ident/'summary.json'
  if r['complete'] and summary.exists():
   for lr in json.loads(summary.read_text())['learning_records']:
    screen=lr.get('selected_plan',{}).get('execution_screen',{});modal=screen.get('coordination_modal_v2');smooth=screen.get('v5_reference_smooth');ant=screen.get('v5_anticipatory');blind=screen.get('v5_blind_shift')
    if smooth:
     if not smooth.get('same_common_speed_coordinate'):errors.append('EXTRA_INDEPENDENT_JOINT_SPEED_MODE')
     elif not -1-1e-12<=smooth['proposed_modal_speed_coordinate']<=1+1e-12:errors.append('REFERENCE_SPEED_COORDINATE_BOX')
     if smooth.get('same_common_speed_coordinate') and smooth['status']=='ACCEPTED':
      expected=np.asarray(smooth['native_parent_pass_velocity'])*(1+.12*smooth['proposed_modal_speed_coordinate']*smooth['weight']);actual=np.asarray(lr['selected_plan']['schedule']['target_dq_rad_s'])
      if np.max(abs(expected-actual))>1e-10:errors.append('ACTUAL_SPEED_NOT_ORIGINAL_COMMON_COORDINATE')
    shift=ant if ant and ant.get('changed') else blind if blind and blind.get('status')=='ACCEPTED' else None
    if shift and modal:
     ph=shift.get('phase',modal['phase']);index=1 if ph=='OUTBOUND' else 3;direction=1. if ph=='OUTBOUND' else -1.;weight=modal['weight'];c=x[index]+shift['delta_deg']/(direction*.3*weight)
     if abs(c)>1+1e-9:errors.append('RELATIVE_COORDINATE_BOX')
 formal=ident not in excluded
 permission.append(dict(id=ident,permission_status='EXPLORATORY_EXCLUDED' if not formal else 'PASS' if not errors else 'FAIL',diagnostics=sorted(set(errors)),original_motion_qualified=r['qualified'],formal_same_domain_eligible=bool(formal and not errors and r['qualified'])))
 if formal and errors:bad.extend([ident+':'+e for e in errors])
put('audit/ACTION_PERMISSION_ALL.json',dict(status='PASS' if not any(r['permission_status']=='FAIL' for r in permission) else 'FAIL',rows=permission,original_outcomes_unchanged=True,exploratory_exclusions_are_not_formal_successes=True))
native_rows=[]
for f in sorted((P/'analysis/native_wrench').glob('*.json')):
 d=json.loads(f.read_text());overlap=d['original_5ms_overlap'];ok=overlap['force_max_abs_error_N']<1e-8 and overlap['moment_max_abs_error_Nm']<1e-8;native_rows.append(dict(id=d['id'],pass_=ok,sampling_s=d['sampling_s'],overlap=overlap))
 if not ok:bad.append('NATIVE_WRENCH_SENSOR_OVERLAP:'+d['id'])
out=dict(status='PASS' if not bad else 'FAIL',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),job_source_and_parent_rows=source_rows,copied_runtime_closure_files=closure_count,unexpected_runtime_changes=relocation,original_guard=guard,original_protocols=protocol,action_permission_audit='audit/ACTION_PERMISSION_ALL.json',native_wrench_overlap=native_rows,errors=bad,zero_new_native_steps=True)
tag='PARTIAL' if '--partial' in sys.argv else 'FINAL';put('audit/SOURCE_AND_PERMISSION_'+tag+'.json',out);print('SOURCE_PERMISSION',tag,out['status'],'jobs',len(source_rows),'closure',closure_count,'errors',bad[:12],flush=True)
assert not bad,'SOURCE_OR_ACTION_PERMISSION_AUDIT_FAILED'
