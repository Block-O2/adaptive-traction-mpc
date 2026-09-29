"""Regression for stopped V2 Rep 11: timestamp subtraction lost precision."""
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'stages/stage5_personalized_motion_learning'
sys.path.insert(0, str(STAGE / 'scripts/high_rom_v1'))
from baseline_accounting_v2 import task_wrench_cost


@pytest.fixture
def preserved_rep11():
    path = STAGE / 'results/zero_value_30rep_baseline_v2/formal_session_01/rep_11'
    if not path.exists():
        pytest.skip('preserved stopped V2 Rep 11 unavailable')
    return path


def test_real_rep11_fixed_interval_matches_unchanged_runtime(preserved_rep11):
    import json
    summary = json.loads((preserved_rep11 / 'summary.json').read_text())
    with np.load(preserved_rep11 / 'trace.npz') as trace:
        costs = task_wrench_cost(trace, trace['stage'] == 'TASK')
    assert abs(costs['J_F_n_s'] - summary['task']['force_integral_n_s']) < 1e-8
    assert costs['interval_count'] == summary['task']['integration_interval_count']
    assert costs['clock_basis'] == 'frozen_5ms_execution_interval_verified_against_recorded_time'


def test_irregular_or_nonfinite_trace_is_rejected(preserved_rep11):
    with np.load(preserved_rep11 / 'trace.npz') as original:
        mask = original['stage'] == 'TASK'
        arrays = {key: original[key].copy() for key in (
            'time_s', 'physical_cuff_force_world_n',
            'physical_cuff_moment_world_nm', 'interval_force_cost_n_s')}
    arrays['time_s'][np.where(mask)[0][2]] += 0.001
    with pytest.raises(ValueError, match='5 ms'):
        task_wrench_cost(arrays, mask)
    arrays['time_s'][np.where(mask)[0][2]] -= 0.001
    arrays['physical_cuff_force_world_n'][np.where(mask)[0][2], 0] = np.nan
    with pytest.raises(ValueError, match='invalid'):
        task_wrench_cost(arrays, mask)
