"""Resource scheduling only: identical immutable proposals and wall cutoff."""
from datetime import datetime,timezone
from native_objective_extension import freeze,expressivity,search
from research_campaign import D,save

save(D/'NATIVE_EXECUTION_RESOURCE_ALLOCATION_V3.json',{'timestamp_utc':datetime.now(timezone.utc).isoformat(),
 'reason':'conditional SCRATCH unit closed; use its freed CPU slot for frozen native proposals',
 'workers':2,'total_live_scientific_rollout_cap':3,'same_saved_proposals_optimizer_budget_cutoff_safety':True,
 'interrupted_parent_drained_current_submitted_batch_before_restart':True})
sources=freeze()
if expressivity(sources):search(sources,workers=2)
