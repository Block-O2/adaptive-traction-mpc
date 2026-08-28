# Rejected Stage 4 compliant distributed-cuff diagnostics

This directory preserves concise negative engineering evidence only.  Neither
implementation is an active or recommended plant.  The explicit four-station
Cartesian penalty model under `explicit_penalty/` crossed the 200 N physical
force gate during the initial hold for every registered length.  Its K/D values
were not tuned to force a successful result.

The root-level `distributed_cuff_080mm.json` and trace preserve a rejected
intermediate soft-connect diagnostic.  Four collinear 3D soft connects produced
redundant constraint rows and non-physical internal load redistribution; this
model is not the reported finite-cuff formulation.

The active follow-on returns to the validated single six-constraint rigid weld.
Finite cuff length is evaluated separately as a deterministic surface-load
decomposition; local surface loads never feed the controller or estimator.

No result in this directory is authoritative or committed.
