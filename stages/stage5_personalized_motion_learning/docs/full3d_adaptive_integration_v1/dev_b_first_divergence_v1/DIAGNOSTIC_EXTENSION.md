# Diagnostic extension after initial matched evaluation

2026-09-23. Preliminary exact-state evaluation of the maximum-jump case
finds 34.834 Nm old/new robot command difference entirely in J-transpose times
the allocator wrench, and zero pose/velocity/bias/clipping difference. The
new model predicts measured-state acceleration substantially better; a 200 ms
physical branch nonetheless exhibits a sub-control-period acceleration and
interface force transient. This supports a narrow diagnostic manipulation.

Add `diagnostic_action_transfer_100ms`: retain the candidate model, geometry,
state estimation, same certified reference and all execution gates; add the
initial old-minus-new Human generalized-action offset, fading with a quintic
over 100 ms (20 control intervals). The offset is computed once from the same
checkpoint, never from hidden truth. Apply the existing allocation and force
filter to the altered action. This is NONDEPLOYABLE and is not promoted to
production. It tests whether the sudden action application causes the local
transient. Its arbitrary diagnostic window is not a tuned or proposed final
controller parameter. Compare at 200 ms and at the existing first 1.5 s segment
endpoint. Longer lifecycle failure remains open unless independently tested.

Initial capture artifact-key failures (`truth_state`, then `robot_q_rad`)
are retained in the first two capture namespaces. Correct NPZ fields are
`evaluation_only_human_state_rad_rad_s` and `cr12_q_rad`; the production code
was unaffected. Final capture namespace is `capture_v3/`.
