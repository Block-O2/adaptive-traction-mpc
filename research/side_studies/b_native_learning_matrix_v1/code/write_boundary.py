from task_bootstrap import *
def main():
 source=json.loads((STUDY/'SOURCE.json').read_text())
 files={str(Path(p).relative_to(STUDY/'source')):h for p,h in source['frozen_files'].items() if '/source/' in p and any(s in p for s in ('runtime_sac_expert_v1','runtime_coordination_residual_v2','coordination_residual_v2.py','human_waypoint_feedback_mpc.py','human_waypoint_scheduler.py','phase3_human_waypoint.py','online_planning.py','terminal_reference.py','execution_policy.py','receipt_reference_governor.py','activation_validation.py'))}
 save(STUDY/'B_BOUNDARY.json',dict(version=1,source_hashes=files,chain=['physical commissioning, causal measurement and frozen estimated belief','B AdaptiveHumanWaypointHWMPCV22 + native terminal reference and local waypoint lattice','native scheduler quintic q/dq/ddq, receipt reference governor and 40ms certified bridge','native original ROM/duration/mechanics/continuous-clearance and tracking-offset certificates','current-model activation revalidation, CR12 sensor-boundary simulated physical execution, native fallback latch'],kept=['B original controls','local predictions','terminal-set search for safety/task feasibility','local candidate goal/change/completion cost','40ms bridge and certified brake fallback'],isolated_P=['planning.Predictor.predict full current-repetition performance model','known_model hidden case parameter provisioning','research V_base and residual value','SearchInterface 2x8 CEM full-repetition cost search','P-specific predicted timing screening'],online_methods='6 current candidate plans; Q predicts direct committed remaining J_F; G supplies 3 candidates; native one-segment decide reused for S and necessary current candidate checks',not_P='Original safety certificates may examine the whole current quintic/escape. They are required native feasibility certificates, not added full-repetition performance search.',information='55D normalized causal observation/reference/cuff wrench and B commissioning beta/residual/geometry; masked candidate/carry/count history; no known truth model or future force/state',zero_gate=str(STUDY/'B_ZERO_GATE.json'),S_scope='S evaluates only current native chunk; pending suffix affects Q but not native local score. No new term, reward, or predictor is created.',authority='K3 spatial knots sampled once at current B interior nominal target. Native opportunities only; HOLD and settled terminal requests skip learning.',import_paths='All traction_mpc/sac_env/campaign_r2/adapter imports must reside under this isolated study; worker rejects planning and known_model imports',source_qualification='Historical frozen B trace exact reproduction required at 1e-10; dirty primary code may differ and was never overwritten'))
 text='''# B native boundary and timing evidence

The B used here is the original commissioned, estimated-belief B. The original
runtime and zero-residual public native runtime reproduce all saved physical
trace fields exactly, including the historical frozen B trace. The untouched
primary working tree is not treated as clean; the study freezes verified
effective source dependencies, including the previous streaming fixes.

B performs physical commissioning/observation, native adaptive waypoint
decision, quintic scheduling, receipt-owned reference governance, continuous
clearance and mechanics certification, current-model activation revalidation,
and coupled MuJoCo execution with its original fallback. All remain active.

The added P implementation (`planning.Predictor`, `known_model`, P V_base,
2x8 CEM and full-plan timing screen) is not copied into this harness. The worker
rejects those module imports. Logging wrappers record native decision,
local evaluation, scheduler and mechanics call counts plus first call stacks.
These original native certificates can examine a future segment/escape, which
does not make them an added repetition-performance predictor.

S reuses the original native single-segment goal-error, waypoint-change,
completion cost and feasibility checks. It scores the same candidates as Q.
It is dimensionless and does not predict remaining force cost. M0 has no new
candidate search. M1 includes the extra candidate generation/evaluation
overhead, separately from M0. G-only is thus defined with the same S.

At an actual native segment endpoint (or phase start) the runtime creates its
request, invokes the public coordination hook, snapshots the selected residual
planner and submits the native worker. Interior handoffs execute the unchanged
40ms certified bridge; the worker must be ready at its end. Command construction,
current-model validation and receipt add to the full activation age. The
independent wall-mode score uses 55ms; the lifecycle also has a general 100ms
expiration rule. Neither implies a blanket 100ms budget for a new network.
K3 knots are not three control periods. No early-computation window is assumed.

Scientific mode blocks computation while physical state is stationary. Its
PASS cannot establish real time PASS. Baseline and matrix retain all native
host timing stages. Coordinator context/generation/G/Q/native validation and
submission are separately recorded. Delayed replay must discard late new
choices and keep the still-legal declared continuation; it cannot backwrite
an action at an already executed time. Full bridge/worker/validation timing
is assessed independently of the neural inference microbenchmark.
'''
 (STUDY/'reports/B_BOUNDARY.md').write_text(text)
 print('B_BOUNDARY_WRITTEN')
if __name__=='__main__':main()
