"""Supplemental valid-snapshot dependency probe, offline synthetic inputs only."""
from pathlib import Path
import sys,os,pickle,json,copy,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_hold_return_critical_path_v1');O=S.parent/'b_fast_runtime_completion_v1';sys.path.insert(0,str(S/'code'));sys.dont_write_bytecode=True
import lean_instrumentation;lean_instrumentation.prime()
import study_common as sc
from traction_mpc_stage4 import estimator_v2 as ma
from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
before=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS
p=O/'inputs/036_N9_V3_A1_C1c_science_nominal_TASK_CAUSAL.pkl';rows=[]
for row in pickle.loads(p.read_bytes()):
 if row['phase']!='RETURN' or 'expected' not in row:continue
 original=op.execute_task_snapshot(row['payload']);planner,args=pickle.loads(row['payload'])
 state=args['current_deployable_state'].copy();state[0]+=1e-6;args['current_deployable_state']=state
 snapshot=dict(planner.planner.tracking_reference_snapshot);snapshot['source_state_rad_rad_s']=state.copy();planner.planner.tracking_reference_snapshot=snapshot
 changed=planner.decide(**args)
 a=sc.clean(original.executed);b=sc.clean(changed.executed)
 rows.append(dict(request_id=row['request_id'],original_target=a['target_q_rad'],changed_target=b['target_q_rad'],target_identical=a['target_q_rad']==b['target_q_rad'],schedule_identical=a['schedule']==b['schedule'],cost_identical=a['total_cost']==b['total_cost'],changed_fields=[k for k in a if a[k]!=b.get(k)],execution_screen_identical=a['execution_screen']==b['execution_screen'],synthetic_offline_perturbation_rad=1e-6,snapshot_source_state_refreshed=True,actuation_authority=False))
out=dict(status='OBSERVED',input_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),rows=rows,model_API_calls=ma.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-before,physics_steps=0,conclusion='These two valid nearby inputs identify preparable base pieces only. They do not establish state independence across the original domain or permit reusing the current tracking-offset screen.')
target=S/'reports/RETURN_CONSISTENT_STATE_DEPENDENCY.json';assert not target.exists();target.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
