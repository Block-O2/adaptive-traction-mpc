import inspect
import json

import numpy as np
import pytest

from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.model_update_alpha_comparison import (
    bounded_update_diagnostics,
)
from traction_mpc_stage5.model_update_max_step_comparison import (
    FIXED_MODEL_UPDATE_ALPHA,
    LONGITUDINAL_CEM_SEEDS,
    MAX_STEP_ARMS,
    MAX_STEP_COMPARISON_CONFIG_PATH,
    baseline_step_0p03_reuse_audit,
    human_id_config_for_max_step,
    load_max_step_contract,
    step_config_equivalence,
)
from traction_mpc_stage5.progressive_personalization import (
    FROZEN_THETA_1,
    ProgressiveLongitudinalArm,
    ProgressiveLongitudinalSession,
    fixed_progress_pacing_status,
)


RUNNER_PATH = (
    STAGE5_ROOT / "scripts" / "run_stage5_model_update_max_step_comparison_v1.py"
)


def _geometry() -> PlanarCuffGeometry:
    rotation = STAGE5_GEOMETRY.world_from_human.rotation
    return PlanarCuffGeometry(
        origin_world_m=STAGE5_GEOMETRY.world_from_human.translation.copy(),
        plane_x_world=rotation[:, 0].copy(),
        joint_axis_world=rotation[:, 1].copy(),
        plane_z_world=rotation[:, 2].copy(),
        hip_plane_m=np.zeros(2),
        thigh_length_m=STAGE5_HUMAN.thigh_length_m,
        knee_to_cuff_in_cuff_m=np.array([STAGE5_HUMAN.sleeve_center_m, 0.0]),
    )


def test_only_preregistered_steps_are_0p03_0p04_0p05() -> None:
    contract = load_max_step_contract()
    assert MAX_STEP_ARMS == {
        "step_0p03": 0.03,
        "step_0p04": 0.04,
        "step_0p05": 0.05,
    }
    assert {
        name: arm["maximum_per_scale_step"]
        for name, arm in contract["arms"].items()
    } == MAX_STEP_ARMS
    with pytest.raises(ValueError, match="only preregistered"):
        human_id_config_for_max_step(0.06)


def test_all_arms_keep_model_update_alpha_exactly_0p25() -> None:
    assert FIXED_MODEL_UPDATE_ALPHA == 0.25
    for step in MAX_STEP_ARMS.values():
        config = human_id_config_for_max_step(step)
        assert config.identifier.smoothing_alpha == 0.25
        assert config.identifier.maximum_update_fraction_of_span == step


def test_maximum_step_is_the_only_identifier_configuration_difference() -> None:
    assert step_config_equivalence() == {
        "changed_identifier_fields": ["maximum_update_fraction_of_span"],
        "all_smoothing_alpha_0p25": True,
        "trust_configs_equal": True,
    }


def test_same_candidate_exposes_expected_cap_effect() -> None:
    candidate = [1.0, 1.0, 1.2]
    results = {
        step: bounded_update_diagnostics(
            FROZEN_THETA_1,
            candidate,
            model_update_alpha=0.25,
            maximum_per_scale_step=step,
        )
        for step in MAX_STEP_ARMS.values()
    }
    assert results[0.03]["actual_limited_displacement"][2] == pytest.approx(0.03)
    assert results[0.04]["actual_limited_displacement"][2] == pytest.approx(0.04)
    assert results[0.05]["actual_limited_displacement"][2] == pytest.approx(
        0.25 * (1.2 - FROZEN_THETA_1[2])
    )
    assert results[0.03]["step_cap_active"][2]
    assert results[0.04]["step_cap_active"][2]
    assert not results[0.05]["step_cap_active"][2]


def test_effectively_uncapped_rule_is_frozen_before_results() -> None:
    contract = load_max_step_contract()
    assert (
        contract["decision_rules"]["effectively_uncapped"]
        == "no per-scale step cap binds in any qualified transition"
    )
    assert "10 percent" in contract["decision_rules"]["material_speed_benefit"]


def test_gamma_native_prefix_and_seed_schedule_are_unchanged() -> None:
    contract = load_max_step_contract()
    assert fixed_progress_pacing_status({}) == {
        "gamma": 0.5,
        "gamma_rate_per_s": 0.0,
    }
    assert contract["controller"]["prefix_backend"] == "native"
    assert contract["controller"]["prefix_times_ms"] == [5, 10, 15, 20]
    assert tuple(contract["repetitions"]["matched_cem_seeds"]) == LONGITUDINAL_CEM_SEEDS


def test_formal_step_0p03_reuse_audit_passes_on_local_result() -> None:
    audit = baseline_step_0p03_reuse_audit()
    if audit.get("reason") == "formal alpha-comparison result is unavailable":
        pytest.skip("ignored local formal alpha-comparison result is unavailable")
    assert audit["eligible"], audit
    assert all(audit["checks"].values())


def test_session_receives_requested_cap_without_other_authority_change() -> None:
    session = ProgressiveLongitudinalSession(
        _geometry(),
        ProgressiveLongitudinalArm.PROGRESSIVE,
        session_id="max-step-test",
        human_id_config=human_id_config_for_max_step(0.04),
    )
    snapshot = session.begin_repetition(1, 0.0)
    np.testing.assert_array_equal(snapshot.active_theta, FROZEN_THETA_1)
    assert session.authority.service.identifier.config.smoothing_alpha == 0.25
    assert (
        session.authority.service.identifier.config.maximum_update_fraction_of_span
        == 0.04
    )


def test_truth_is_absent_from_online_measurement_and_observe_inputs() -> None:
    measurement = inspect.getsource(ProgressiveLongitudinalSession._measurement)
    observe = inspect.getsource(ProgressiveLongitudinalSession.observe)
    assert "truth" not in measurement.lower()
    assert 'payload["truth' not in observe.lower()
    assert '"truth_consumed": False' in observe


def test_formal_runner_reuses_A_and_freshly_runs_only_B_C() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "baseline_step_0p03_reuse_audit" in source
    assert 'for name in ("step_0p04", "step_0p05")' in source
    assert "--execute-formal-fresh-b-c" in source
    assert 'prefix_backend="native"' in source


def test_contract_is_strict_json_and_authorized_before_execution() -> None:
    payload = json.loads(MAX_STEP_COMPARISON_CONFIG_PATH.read_text(encoding="utf-8"))
    assert payload["status"] == "PREREGISTERED_FORMAL_EXECUTION_AUTHORIZED"
    assert payload["only_scientific_variable"] == "maximum_per_scale_step"


def test_acceleration_monitor_contract_remains_frozen() -> None:
    contract = load_max_step_contract()
    assert contract["controller"]["acceleration_monitor_changed"] is False
    assert contract["fixed_open_issues"]["acceleration_monitor"] == (
        "A-MONITOR-UNRESOLVED"
    )
