import numpy as np

from traction_mpc_stage4.estimator_v2 import (
    BaseParameterHumanModel,
    PlanarCuffGeometry,
    nominal_base_parameters,
)
from traction_mpc_stage4.minimal_adaptation import effective_base_parameters
from traction_mpc_stage5.geometry import STAGE5_GEOMETRY
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.human_identification_reduced import (
    ReducedIntegralScaleIdentifier,
    Stage5ReducedHumanIDConfig,
)
from traction_mpc_stage5.human_model_update import (
    build_bounded_human_model_transition,
    classify_post_update_evidence,
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


def test_historical_damping_candidate_reproduces_stored_bounded_successor() -> None:
    identifier = ReducedIntegralScaleIdentifier()
    transition = build_bounded_human_model_transition(
        identifier,
        np.ones(3),
        np.array([1.0005843909854664, 1.010424686528112, 1.1934798034676337]),
        predecessor_version="fixed-nominal-v1",
        candidate_version="damping-attempt-0",
        successor_version="damping-successor-1",
    )
    assert np.allclose(
        transition.successor_scales,
        [1.0000584390985465, 1.0010424686528112, 1.0193479803467633],
    )
    assert transition.limiting_rule_per_parameter == (
        "smoothing_alpha",
        "smoothing_alpha",
        "smoothing_alpha",
    )
    assert not any(transition.step_limit_active)
    assert transition.applied_to_control is False
    assert transition.provisional_only is True


def test_maximum_step_is_componentwise_fraction_of_parameter_span() -> None:
    identifier = ReducedIntegralScaleIdentifier()
    transition = build_bounded_human_model_transition(
        identifier,
        np.ones(3),
        np.full(3, 1.5),
        predecessor_version="model-0",
        candidate_version="candidate-0",
        successor_version="model-1-provisional",
    )
    assert np.allclose(transition.maximum_step_per_parameter, [0.03, 0.03, 0.03])
    assert np.allclose(transition.successor_scales, [1.03, 1.03, 1.03])
    assert all(transition.step_limit_active)


def test_bounded_successor_is_a_finite_positive_definite_three_scale_model() -> None:
    identifier = ReducedIntegralScaleIdentifier()
    transition = build_bounded_human_model_transition(
        identifier,
        np.ones(3),
        np.array([1.1, 1.15, 1.2]),
        predecessor_version="model-0",
        candidate_version="candidate-0",
        successor_version="model-1-provisional",
    )
    scales = np.asarray(transition.successor_scales)
    assert np.all(scales >= identifier.lower)
    assert np.all(scales <= identifier.upper)
    model = BaseParameterHumanModel(
        geometry=_geometry(),
        beta=effective_base_parameters(
            scales, nominal_base_parameters(STAGE5_HUMAN)
        ),
        rom_human=STAGE5_HUMAN,
    )
    assert model.minimum_mass_matrix_eigenvalue() > 1.0e-6


def test_post_update_evidence_reuses_existing_future_validation_bounds() -> None:
    config = Stage5ReducedHumanIDConfig().trust
    positive = classify_post_update_evidence(
        -np.ones(config.minimum_clean_blocks), config=config
    )
    negative = classify_post_update_evidence(
        np.ones(config.minimum_clean_blocks), config=config
    )
    neutral = classify_post_update_evidence(
        np.zeros(config.minimum_clean_blocks), config=config
    )
    insufficient = classify_post_update_evidence(
        -np.ones(config.minimum_clean_blocks - 1), config=config
    )
    assert positive["outcome"] == "positive"
    assert negative["outcome"] == "negative"
    assert neutral["outcome"] == "neutral"
    assert insufficient == {
        "outcome": "neutral",
        "reason": "insufficient_genuinely_later_blocks",
        "decision_block_count": None,
        "available_block_count": config.minimum_clean_blocks - 1,
        "looks": [],
    }
