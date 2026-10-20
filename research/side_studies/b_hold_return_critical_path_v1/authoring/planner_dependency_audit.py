"""Offline saved original causal payloads; no live plant, no new request."""
from pathlib import Path
import sys,os,pickle,json,time,hashlib,copy
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');O=S.parent/'b_fast_runtime_completion_v1';sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
start=time.time()
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc
from traction_mpc_stage4 import estimator_v2 as ma
from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
baseline=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
path=O/'inputs/036_N9_V3_A1_C1c_science_nominal_TASK_CAUSAL.pkl'
rows=pickle.loads(path.read_bytes());output=[]
for row in rows:
 if row['phase']!='RETURN' or 'expected' not in row:continue
 planner,args=pickle.loads(row['payload']);expected=pickle.loads(row['expected'])
 actual=op.execute_task_snapshot(row['payload'])
 # A synthetic OFFLINE input perturbation probes dependency, never enters a run.
 perturbed=copy.deepcopy(args)
 statekeys=[k for k in args if 'state' in k and k!='current_reference_state']
 statekey=next(k for k in statekeys if hasattr(args[k],'shape') and args[k].shape==(4,))
 perturbed[statekey][0]+=1e-6
 clone=pickle.loads(pickle.dumps(planner,protocol=5))
 try:changed=clone.decide(**perturbed);rejection=None
 except ValueError as error:changed=None;rejection=str(error)
 a=sc.clean(actual);e=sc.clean(expected);a.pop('runtime_ms',None);e.pop('runtime_ms',None)
 original=sc.clean(actual.executed);other=None if changed is None else sc.clean(changed.executed)
 output.append(dict(request_id=row['request_id'],source_sample_s=row['original_source_sample_s'],argument_keys=list(args),state_key=statekey,current_state=args[statekey].tolist(),current_reference=args['current_reference_state'].tolist(),selected_target=actual.executed.target_q_rad.tolist(),saved_replay_mathematics_bit_exact=a==e,perturbation_rad=1e-6,current_state_snapshot_mismatch_rejection=rejection,selected_record_changes=None if other is None else original!=other,selected_target_changes=None if other is None else original['target_q_rad']!=other['target_q_rad'],changed_record_fields=[] if other is None else [k for k in original if original[k]!=other.get(k)],authority='offline dependency probe only; no actuation'))
out=dict(status='PASS' if output and all(r['saved_replay_mathematics_bit_exact'] for r in output) else 'FAIL',input_path=str(path),input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=output,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-baseline,import_warm_counter=baseline,physics_steps=0,wall_s=time.time()-start,conclusion='Fixed task endpoint is static. Original RETURN native decision includes current state, current reference, belief, remaining phase budget, previous decision state and current tracking-offset screen. Matching two selected targets does not prove a whole result/certificate is static.')
(S/'reports/RETURN_PLANNER_DEPENDENCY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
