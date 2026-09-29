"""Regression for phase-local exploration horizon indexing in worker snapshots."""
from __future__ import annotations
import pickle
import sys
from pathlib import Path
from types import SimpleNamespace

STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'scripts/high_rom_v1'))
sys.path.insert(0,str(STAGE/'src'))
sys.path.insert(0,str(STAGE.parents[0]/'stage4_adaptive_control/src'))
sys.path.insert(0,str(STAGE.parents[0]/'stage3_full3d/src'))
from safe_action_horizon_adapter_v1 import snapshot_exploration_task_call, WEIGHTS
from traction_mpc_stage5.task import TaskPhase


def test_worker_snapshot_has_phase_index_without_history():
    original=SimpleNamespace(planner=SimpleNamespace(decisions=[SimpleNamespace(phase=TaskPhase.OUTBOUND) for _ in range(3)]+[SimpleNamespace(phase=TaskPhase.RETURN)]),belief_sequences_used=[1,2])
    cloned,args=pickle.loads(snapshot_exploration_task_call(original,{'phase':TaskPhase.OUTBOUND}))
    assert cloned.planner.exploration_phase_index==3
    assert cloned.planner.decisions==[]
    assert cloned.belief_sequences_used==[]
    assert len(original.planner.decisions)==4
    assert [len(WEIGHTS[h]) for h in ('H1','H2','H3','H4')]==[1,3,6,6]


def test_safety_rejected_rollout_is_classified_as_infeasible():
    from run_safe_action_horizon_rollout_v1 import classify_abort
    assert classify_abort({'abort_reason':'NO_FEASIBLE_WAYPOINT:EXPLORATION_ACTION_INFEASIBLE:shank-table clearance'})=='INFEASIBLE'
    assert classify_abort({'abort_reason':'PHYSICAL_FORCE_LIMIT'})=='INVALID'
