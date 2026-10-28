from pathlib import Path
import json, hashlib, subprocess, time, shutil
R=Path('/home/hank/ihear-lab/representation_execution_v3/runtime/source')
S=R/'stages/stage5_personalized_motion_learning'
W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/coordination_research_interface_v1')
D=S/'docs/coordination_research_interface_v1'; P=S/'scripts/coordination_research_interface_v1'
SRC=S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a):return subprocess.check_output(['git','-C',str(R),*a],text=True)
def save(n,x):
 for d in (W/'output',D):
  d.mkdir(parents=True,exist_ok=True);(d/n).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
assert not (D/'CONTRACT.json').exists(),'NO_OVERWRITE'
before=dict(branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),status=git('status','--short'),index_sha256=sha(R/'.git/index'),cached_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(R),'diff','--cached','--binary'])).hexdigest())
save('GIT_BEFORE.json',before)
protected={str(p.relative_to(R)):sha(p) for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning') for p in (R/'stages'/stage/'src').rglob('*') if p.is_file() and p.suffix in ('.py','.xml')}
protected.update({str(p.relative_to(R)):sha(p) for p in (S/'configs').rglob('*') if p.is_file()})
historical={str(p.relative_to(R)):sha(p) for name in ('single_human_sac_expert_v1','best_known_coordination_search_v2','coordination_pacing_exploration_v1','adaptive_human_online_interface_v1') for p in (S/'docs'/name).rglob('*') if p.is_file()}
save('PROTECTED.json',dict(source=protected,historical=historical))
git('switch','-c','codex/coordination-research-interface-v1')
contract=dict(schema='coordination_research_interface_v1',started_unix=time.time(),hard_cutoff_unix=time.time()+8*3600,branch='codex/coordination-research-interface-v1',B='current unmodified R2 old_nominal model controller; commissioning_only; native planner plus R2 9/1/9 clocks',question='Can endpoint-zero differential residuals preserve B pacing, express historical coordination, and branch complete same-state continuation costs?',category='interface development and smoke; one previously exposed nominal Human; no held-out/generalization claim',initial_condition_seed=20261003,truth_firewall='Only causal reference/belief/task inputs propose candidates; MuJoCo hidden state retained solely for branch restoration and evaluator',timing='R2 phase minima 9/1/9 s; each <= minimum + .020 s; no post-task wait, no segment count gate',metrics=['unchanged physical audit','5ms left J_F quadrature','force/moment','clearance','phase durations','common-mode reference error','joint path error'],gates=dict(A='zero reference and physical arrays atol 1e-10; metrics atol 1e-6',B='historical pure differential fit RMS normalized <= .02; valid complete MATCHED execution; disclose path error',C='same as B for CEM; no historic numeric reproduction claim',D='positive/negative/reversal/catch-up/independent RETURN; continuous executable residuals',E='all same-state branches identical before candidate; complete continuation valid; timing R2; distinguish outcomes'),budget=dict(branch_snapshots=4,candidates_per_snapshot=3,branch_rollouts=12,physics_owners=1,training_steps=0),continuation_policy_id='B_pacing_zero_residual_after_declared_C2_chunk_v1',scientific_changes='None to B source, Human physics, thresholds, task timing or history; additive research code only',stop='hard 8h; no training; preserve failed gates; E/V promotion requires all user A-H gates')
save('CONTRACT.json',contract);shutil.copy2(__file__,P/'preflight.py') if P.exists() else P.mkdir(parents=True)
base=(SRC/'runtime_sac_expert_v1.py').read_text()
# Versioned runtime adds one research route; the entire zero path is unchanged.
new=base.replace('    sac_hooks: Any = None,','    sac_hooks: Any = None,\n    coordination_interface: Any = None,')
assert new!=base
needle='        if online_command_period_s is not None:\n            from .online_reference import OnlineReferenceOwner'
route='''        if coordination_interface is not None and coordination_interface.replay_mode:
            try:
                reference, active_schedule, schedule_start_time = coordination_interface.reference(
                    phase=task_state.phase, physical_now=physical_now, task_start_time=task_start_time,
                    task_state=task_state, spec=spec, belief=belief, clearance=clearance,
                    scheduler=scheduler, owned=(reference_state[:2],reference_state[2:],reference_acceleration),
                    estimated_state=state, runtime=runtime)
                reference_governor = None
                actuation_enabled = True
            except ValueError as error:
                task_state = abort_episode(task_state, 'COORDINATION_NO_CERTIFIED_CONTINUATION:'+str(error))
                continue
        elif online_command_period_s is not None:
            from .online_reference import OnlineReferenceOwner'''
assert base.count(needle)==1;new=new.replace(needle,route)
# The branch callback runs only on the single main physics thread, immediately
# before any candidate mutation, and can inspect all live locals.
needle='        reference_state = np.concatenate([reference.q_rad, reference.dq_rad_s])\n        reference_acceleration = reference.ddq_rad_s2.copy()\n        force_norm = '
replacement='''        if coordination_interface is not None:
            coordination_interface.boundary(locals())
        reference_state = np.concatenate([reference.q_rad, reference.dq_rad_s])
        reference_acceleration = reference.ddq_rad_s2.copy()
        force_norm = '''
assert new.count(needle)==1;new=new.replace(needle,replacement)
# Keep relative imports in a generated module under the original package;
# import through spec with a qualified package name, no production write.
(P/'runtime_coordination_v1.py').write_text(new)
save('RUNTIME_PATCH.json',dict(base_sha256=sha(SRC/'runtime_sac_expert_v1.py'),generated_sha256=sha(P/'runtime_coordination_v1.py'),zero_route='identical original runtime except read-only boundary callback',replay_route='frozen causal B q/dq/ddq tape plus C2 differential; inherited _execute_interval and task manager'))
save('STATE.json',dict(status='IMPLEMENTING',training_steps=0,next_action='Implement schedule, certify replay, run A-D and exactly 12 fork continuations'))
print(json.dumps(dict(branch=git('branch','--show-current').strip(),protected=len(protected),history=len(historical),docs=str(D))))
