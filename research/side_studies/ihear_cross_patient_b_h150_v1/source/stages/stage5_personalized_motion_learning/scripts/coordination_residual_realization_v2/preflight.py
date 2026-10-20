from common import *
import subprocess
SRC=S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1'
def git(*a):return subprocess.check_output(['git','-C',str(R),*a],text=True)
assert not (D/'CONTRACT.json').exists(),'NO_OVERWRITE'
save('GIT_BEFORE.json',dict(branch=git('branch','--show-current').strip(),head=git('rev-parse','HEAD').strip(),status=git('status','--short'),index_sha256=sha(R/'.git/index'),cached_diff_sha256=hashlib.sha256(subprocess.check_output(['git','-C',str(R),'diff','--cached','--binary'])).hexdigest()))
protected={str(p):sha(p) for stage in ('stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning') for p in (R/'stages'/stage/'src').rglob('*') if p.is_file() and p.suffix in ('.py','.xml')}
for root in [S/'configs',*(S/k/'coordination_research_interface_v1' for k in ('docs','scripts','results')),W.parent/'coordination_research_interface_v1']:
 protected.update({str(p):sha(p) for p in root.rglob('*') if p.is_file()})
save('PROTECTED.json',protected)
git('switch','-c','codex/coordination-residual-realization-v2')
save('CONTRACT.json',dict(version='native_scheduler_coordination_residual_v2',started_unix=time.time(),hard_cutoff_unix=time.time()+8*3600,B='unchanged runtime_sac_expert_v1 model-based commissioning_only with R2 MATCHED clocks',category='development physical gates; previously exposed single nominal Human; no held-out claim',inputs='native nominal target and causal deployable request state/reference/belief only',truth_firewall='full hidden state only fork/evaluation, never residual generation',metrics=['native physical/scientific evaluator','5ms left force integral','force peak mean RMS','moment integral peak','clearance','R2 timing','native C2 boundary','residual acceptance and activation'],amplitudes=[.01,.005,.0025,.001],minimal=['hip','knee','catchup','reversal','independent'],max_minimal_rollouts=20,structural_repair_limit=4,zero_gate='all scientific arrays exact or atol1e-10, JF atol1e-6, timing safety wait/ownership equal',historical_gate='actual nonzero native execution; path RMS <=.02 normalized; complete valid MATCHED',branch_gate='4 snapshots x zero/hip/knee; full-state hash equal; actual distinct references; valid MATCHED; some remaining costs differ',endpoint='HOLD disabled; nominal terminal target => residual exactly0; knots endpoints0; no hidden clip',scientific_changes='none to B, plant, objective, safety, timing, history',training_steps=0,physics_owners=1))
P.mkdir(parents=True,exist_ok=True)
base=(SRC/'runtime_sac_expert_v1.py').read_text()
new=base.replace('    sac_hooks: Any = None,','    sac_hooks: Any = None,\n    coordination_interface: Any = None,')
needle='    planner_type = (TerminalSetHumanWaypointPlannerV1'
assert new.count(needle)==1
new=new.replace(needle,'    from .coordination_residual_v2 import NativeResidualPlannerV2\n    planner_type = (NativeResidualPlannerV2')
needle='    adaptive_planner = AdaptiveHumanWaypointHWMPCV22(planner)'
assert new.count(needle)==1
new=new.replace(needle,'    planner.residual_spec = {} if coordination_interface is None else coordination_interface.action\n'+needle)
needle='                payload = snapshot_task_call(adaptive_planner, arguments)'
assert new.count(needle)==1
new=new.replace(needle,'                if coordination_interface is not None:\n                    coordination_interface.decision_boundary(locals())\n                    if getattr(coordination_interface, "branch_output_dir", None) is not None:\n                        output_dir = coordination_interface.branch_output_dir\n'+needle)
needle='        reference_state = np.concatenate([reference.q_rad, reference.dq_rad_s])\n        reference_acceleration = reference.ddq_rad_s2.copy()\n        force_norm = '
assert new.count(needle)==1
new=new.replace(needle,'        if coordination_interface is not None:\n            coordination_interface.boundary(locals())\n'+needle)
(SRC/'runtime_coordination_residual_v2.py').write_text(new)
shutil.copy2(W/'coordination_residual_v2.py',SRC/'coordination_residual_v2.py')
for p in W.glob('*.py'):shutil.copy2(p,P/p.name)
save('RUNTIME_PATCH.json',dict(base_sha256=sha(SRC/'runtime_sac_expert_v1.py'),new_sha256=sha(SRC/'runtime_coordination_residual_v2.py'),route='native planner subclass; zero directly returns super decision; unchanged scheduling and activation'))
print('PREFLIGHT_COMPLETE',flush=True)
