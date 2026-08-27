from __future__ import annotations

import numpy as np

from traction_mpc_stage4.dynamics_failure_audit import bound_diagnostics
from traction_mpc_stage4.integral_identifier import (
    AccumulatedIntegralBaseDynamicIdentifier,
)


def test_bound_diagnostics_reports_active_bound_and_unconstrained_pressure() -> None:
    identifier = AccumulatedIntegralBaseDynamicIdentifier()
    candidate = identifier.population_prior.copy()
    unconstrained = identifier.population_prior.copy()
    index = 10
    candidate[index] = identifier.lower[index]
    unconstrained[index] = identifier.lower[index] - 0.25 * identifier.span[index]
    records = bound_diagnostics(identifier, candidate, unconstrained)
    selected = next(item for item in records if item["index"] == index)
    assert selected["constrained_hit"]
    assert selected["direction"] == "lower"
    np.testing.assert_allclose(
        selected["unconstrained_violation_fraction_of_span"], 0.25
    )


def test_bound_diagnostics_keeps_unconstrained_violation_distinct_from_hit() -> None:
    identifier = AccumulatedIntegralBaseDynamicIdentifier()
    candidate = identifier.population_prior.copy()
    unconstrained = identifier.population_prior.copy()
    index = 0
    unconstrained[index] = identifier.lower[index] - 0.1 * identifier.span[index]
    records = bound_diagnostics(identifier, candidate, unconstrained)
    selected = next(item for item in records if item["index"] == index)
    assert not selected["constrained_hit"]
    assert selected["unconstrained_violation"] > 0.0


def test_unconstrained_pressure_does_not_depend_on_solver_boundary_slack() -> None:
    identifier = AccumulatedIntegralBaseDynamicIdentifier()
    index = 10
    unconstrained = identifier.population_prior.copy()
    unconstrained[index] = identifier.lower[index] - 0.2 * identifier.span[index]
    pressures = []
    hits = []
    for slack in (0.5e-7, 5.0e-7):
        candidate = identifier.population_prior.copy()
        candidate[index] = identifier.lower[index] + slack
        selected = next(
            item
            for item in bound_diagnostics(identifier, candidate, unconstrained)
            if item["index"] == index
        )
        pressures.append(selected["unconstrained_violation_fraction_of_span"])
        hits.append(selected["constrained_hit"])
    np.testing.assert_allclose(pressures, [0.2, 0.2])
    assert hits == [True, False]
