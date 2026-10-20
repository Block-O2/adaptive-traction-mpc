"""Freeze bounded research-only computation revision before fresh evidence."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
BASE=ROOT/'stages/stage5_personalized_motion_learning'
DOC=BASE/'docs/value_learning_research_v1'
SCRIPT=BASE/'scripts/value_learning_v1'
paths=[SCRIPT/'research_adapter.py',SCRIPT/'latency_test_lazy_comparator.py',
       SCRIPT/'latency_capture.py',SCRIPT/'latency_replay_benchmark.py',
       SCRIPT/'latency_gate_builder.py',SCRIPT/'research_activation.py',
       BASE/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/terminal_reference.py',
       BASE/'src/traction_mpc_stage5/human_waypoint_feedback_mpc.py',
       BASE/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/safe_fallback.py',
       BASE/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/activation_validation.py',
       DOC/'models/ridge_full_100.0.npz',
       BASE/'results/value_learning_research_v1/latency_gate_v2/SUBSET0236_ACTUAL_MOVING_COMPUTATION_GATE.json']
result={'schema':'bounded_development_latency_revision_v3','status':'FROZEN_BEFORE_FRESH_CAPTURE_AND_CLEAN_RUN',
        'frozen_utc':datetime.now(timezone.utc).isoformat(),'repair_cycle':6,
        'configuration':{'mode':'VALUE_PATTERN','legacy_candidate_limit':1,'proposal_indices':[0,2,3,6],
                         'proposal_bank_source_indices':[0,2,3,6],'lazy_legacy_comparator_on_committed':True},
        'change':'Committed MATCHED VALUE_PATTERN uses inherited terminal/setup guards and one unchanged committed _evaluate precheck reused by existing screen_target; baseline comparator deferred until committed precheck/matched hard screen rejection',
        'preserved':['initial ranking eager legacy','HOLD eager legacy','native eager legacy','branch eager legacy',
                     'original terminal-reference selection/cache revalidation','original candidate _evaluate','original fixed-duration and causal clearance checks',
                     'escape preparation','authority and original source-epoch activation validation','strict35ms moving opportunity and100ms source expiry'],
        'comparator_logging':'Successful lazy continuation has no baseline greedy comparison; greedy points to chosen research target and absent comparator is explicit, never a zero baseline cost claim',
        'development_semantic_tests':'4 actual frozen snapshot comparisons plus3 activation regressions PASS; real J equivalence awaits new clean rollout',
        'previous_v2_failure_preserved':True,'outlier_discard_or_deadline_relaxation':False,
        'fresh_actual_moving_replay_and_clean_rollout_required':True,'pilot_gate_until_new_actual_evidence':'CLOSED',
        'hardware_realtime_qualified':False,
        'source_original_content_sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
output=DOC/'LATENCY_LAZY_COMPARATOR_REVISION_V3.json'
with output.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(str(output))
