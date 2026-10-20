from pathlib import Path
import json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
selection=json.loads((S/'FROZEN_SELECTION.json').read_text())
assert not any(p.name.startswith(('W1_','W2_','repeat_')) for p in (S/'source/results').iterdir())
(S/'DIAGNOSTIC_REPLAY_REGISTERED.json').write_text(json.dumps(dict(unix=time.time(),frozen_selection_unix=selection['unix'],frozen_diagnostic=selection['diagnostic']['id'],registered_after_freeze_before_any_validation=True,earlier_registration_guard_failure='overly strict no-frozen-file precondition; no physics had run; corrected to allow exact frozen diagnostic replay without selection changes',method='Repeat the lowest-force motion-failing frozen diagnostic under same original full dynamics and preserve complete native raw; ordinary original diagnostic may already be compacted after full audit',extra_physics=1,total_reserved_maximum=12,no_reselection=True,no_heldout_seen=True,purpose='Retain key full physical trace plus exact archived control/human-state replay scope without claiming missing original full native rows can be rechecked'),indent=2)+'\n')
print('DIAGNOSTIC_REPLAY_REGISTERED')
