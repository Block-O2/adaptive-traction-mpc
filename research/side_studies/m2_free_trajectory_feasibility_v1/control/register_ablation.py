from pathlib import Path
import json,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_free_trajectory_feasibility_v1')
assert not (S/'FROZEN_SELECTION.json').exists()
assert not any(p.name.startswith(('W1_','W2_','repeat_')) for p in (S/'source/results').iterdir())
(S/'POST_FREEZE_DIAGNOSTICS_REGISTERED.json').write_text(json.dumps(dict(unix=time.time(),methods=['matched no-free-velocity ablation if selected velocity coefficients are nonzero','matched no-common-progress ablation if selected common coefficients are nonzero'],max_additional_physics=2,all_in_global_96_attempt_ledger=True,main_selection_not_updated=True,holdout_params_unchanged=True,no_heldout_seen=True,purpose='attribute useful reference freedom after exact repeat, not search or heldout repair',reserved_total_maximum=11),indent=2)+'\n')
print('ABLATIONS_REGISTERED_BEFORE_SELECTION')
