# Pre-correction diagnostic provenance

This directory retains only concise scientific records from diagnostics that
explained the historical High-ROM execution behavior. These artifacts are not
the current baseline and must not be used to revive the old 200 N/BRAKE
limitation as a corrected-result claim.

- `execution_stack_v2/`: final event-stage decomposition tables and summary.
- `twist_estimator_v2/`: final velocity-estimator metrics and summary.
- `velocity_feedback_path_v1/`: reconstruction of the historical low-level
  robot velocity-feedback path.
- `matched_temporal_counterfactual_v1/`: matched-time counterfactual tables.
- `p1_120_120_event_v1/`: concise record of the historical approximately
  222 N P1 event.
- `corrected_campaign_registration/`: registration, migration, and campaign
  completion records for the corrected baseline.

All large NPZ windows and diagnostic figures were omitted because their
conclusions are represented by these REPORT/JSON/CSV/manifests and the original
state remains recoverable from Git history or the external raw archive hashes.
The corrected 40/80, 90/120, and 120/120 baseline is authoritative: it no
longer shows the old BRAKE/200 N limitation, and P1's remaining benefit is
trajectory-dependent transient smoothing rather than feasibility.
