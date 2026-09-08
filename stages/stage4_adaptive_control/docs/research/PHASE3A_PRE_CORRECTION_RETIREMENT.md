# Phase-3A pre-correction retirement note

Phase-2 closeout removed the tracked binary/raw products and executable
one-off tooling for the historical High-ROM campaigns. The old Rigid BRAKE
events and the approximately 222 N P1 event remain pre-correction diagnostic
history; they are not evidence for the corrected velocity-feedback baseline.
Their compact reports, summaries, tables, manifests, checksums, approved
Specs, and Git history remain available.

The seven frozen-spec test groups retired by this closeout were:

- `test_phase3a_soft_qualification.py`;
- `test_progressive_interface.py`;
- `test_progressive_relaxed_ab.py`;
- `test_progressive_exploratory_ab.py`;
- `test_progressive_40_80_ab.py`;
- `test_progressive_90_120_ab.py`;
- `test_progressive_120_120_ab.py`.

These tests intentionally locked pre-correction
`traction_mpc_stage4/executable_command.py` hashes. Their hashes were not
updated. The coarse-ROM and velocity-path one-off runner tests were retired
with their source campaigns. The completed corrected-campaign runner test was
also retired because clean-clone result reproduction now starts from the
tracked compact sources rather than rerunning a scientific trajectory.

Active Phase-3A regression covers the corrected robot joint/Jacobian
control-feedback velocity contract, compact-source integrity, neutral
frozen-state rendering support, professor-report regeneration, and force-map
regeneration. No controller, model, physical, trajectory, solver, timing,
seed, or threshold parameter changed during this retirement.
