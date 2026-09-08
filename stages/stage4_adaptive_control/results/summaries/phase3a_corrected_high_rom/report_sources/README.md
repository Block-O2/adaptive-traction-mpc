# Compact professor-report and force-map sources

These tracked NPZ files are the minimum frozen inputs used by the final
Phase-3A builders. They contain no controller rollout capability.

- Each case file stores the exact video frame samples used by the report,
  tracking paths capped at 700 samples, and force-overlay paths capped at 420
  samples.
- `force_model_inputs.npz` stores the frozen geometry and dynamic-base vectors
  used to reproduce the analytic force landscape.
- `manifest.json` records array schemas, file hashes, original raw-source
  hashes, and the unchanged-science declaration.

The export preserves the old builder's latest-sample/ZOH and integer-linspace
selection rules. Regeneration consumes only these files and the reviewed
compact comparison/map package; it does not read local corrected or historical
progressive raw campaign directories.
