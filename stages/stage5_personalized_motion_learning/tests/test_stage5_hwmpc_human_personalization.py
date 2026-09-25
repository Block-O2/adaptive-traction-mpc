import json

import numpy as np

from traction_mpc_stage5.config import STAGE5_ROOT
from traction_mpc_stage5.human import STAGE5_HUMAN
from traction_mpc_stage5.progressive_personalization import (
    ProgressiveLongitudinalArm,
    ProgressiveLongitudinalSession,
    initial_population_prior_model,
)
from traction_mpc_stage5.task import PROVISIONAL_LOW_MODERATE_GOAL_TASK
from validate_stage5_human_waypoint_shadow import _prepare_runtime
from validate_stage5_hwmpc_human_personalization import _geometry
from validate_stage5_hwmpc_human_personalization import (
    _all_activated_successors_have_positive_post_update_evidence,
)


CONFIG_PATH = (
    STAGE5_ROOT / "configs" / "stage5_hwmpc_human_personalization_v1.json"
)


def test_hwmpc_personalization_config_freezes_force_neutral_r_contract() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["status"] == "PREREGISTERED_BEFORE_HWMPC_PERSONALIZATION_OUTCOMES"
    assert config["trajectory"]["frozen_support_interval"] == [-0.24, 0.55]
    assert config["trajectory"]["selection_is_force_neutral"]
    assert config["acceptance"][
        "require_positive_post_update_evidence_for_each_activated_model"
    ]
    assert config["scope"]["cumulative_force_objective"] is False
    assert config["scope"]["force_based_r_selection"] is False
    assert config["scope"]["value_learning"] is False
    assert config["scope"]["rl"] is False


def test_waypoint_runtime_binds_explicit_active_human_model_and_version() -> None:
    session_id = "personalized-runtime-test"
    session = ProgressiveLongitudinalSession(
        _geometry(),
        ProgressiveLongitudinalArm.PROGRESSIVE,
        session_id=session_id,
        initial_active_model=initial_population_prior_model(session_id),
    )
    session.begin_repetition(1, 0.0)
    active_model = session.control_human_model
    runtime = _prepare_runtime(
        "personalized-runtime-test",
        np.asarray(
            PROVISIONAL_LOW_MODERATE_GOAL_TASK.start_return_target_rad,
            dtype=float,
        ),
        truth_human=STAGE5_HUMAN,
        control_human_model=active_model,
        control_human_model_version=session.active_model.model_id,
    )

    assert runtime["human_model"] is active_model
    assert runtime["human_model_version"] == session.active_model.model_id
    assert runtime["contract"].human_model is active_model


def test_positive_post_update_evidence_is_required_for_every_successor() -> None:
    def result(support: str, evidence_id: str | None) -> dict:
        return {
            "arms": {
                "progressive": {
                    "authority": {
                        "lineage": {
                            "prior": {
                                "update_index": 0,
                                "post_update_support": "positive",
                                "post_update_evidence_id": None,
                            },
                            "successor": {
                                "update_index": 1,
                                "post_update_support": support,
                                "post_update_evidence_id": evidence_id,
                            },
                        }
                    }
                }
            }
        }

    assert _all_activated_successors_have_positive_post_update_evidence(
        result("positive", "future-evidence")
    )
    assert not _all_activated_successors_have_positive_post_update_evidence(
        result("neutral", None)
    )
