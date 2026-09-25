from __future__ import annotations

from audit_stage5_control_abstraction import build_summary


def test_control_abstraction_audit_is_shadow_only_and_evidence_backed() -> None:
    result = build_summary()

    assert result["decision"].startswith("CA2-A")
    assert result["production_behavior_changed"] is False
    assert all(not changed for changed in result["scope_invariants"].values())
    assert result["saved_evidence"]["task_contact_role"][
        "registered_contact_free"
    ]
    assert result["saved_evidence"]["task_contact_role"][
        "complete_ur10e_contact_free"
    ]
    assert result["saved_evidence"]["support_domain"][
        "continuous_phase_spanning_route"
    ] is False


def test_recommended_contract_moves_fast_execution_out_of_mpc() -> None:
    result = build_summary()
    option = result["candidate_abstractions"]["A_human_waypoint_velocity"]

    assert "robot q/dq propagation" in option["prediction_details_removed"]
    assert "interface deformation recurrence" in option["prediction_details_removed"]
    assert result["one_next_implementation"]["name"] == (
        "HumanWaypointMPCShadowContractV1"
    )
    assert "production activation" in result["one_next_implementation"][
        "must_not_include"
    ]
