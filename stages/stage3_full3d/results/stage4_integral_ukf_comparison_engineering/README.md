# Integral identifier / state-UKF engineering comparison

This directory contains exactly six registered runs: architectures A and B
under ideal, noise, and noise-plus-synchronized-10-ms-delay sensing. The two
architecture subdirectories preserve JSON summaries and compressed traces.

`frontend_transparency.json` is the prerequisite ideal-boundary audit;
`comparison_summary.json` and `summary.md` are the compact aggregate. These
are uncommitted engineering artifacts, not formal or authoritative evidence.

See `../../docs/STAGE4_INTEGRAL_UKF_COMPARISON.md` for the formulation, fixed
UKF Q/R, comparison, decision, and reproduction command.
