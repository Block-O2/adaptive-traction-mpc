"""Integration tests on preserved V1 Rep 7; real scorer, no scorer mocks."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'stages/stage5_personalized_motion_learning'
SCRIPT = STAGE / 'scripts/high_rom_v1'
SOURCE = STAGE / 'results/zero_value_30rep_baseline_v1/formal_session_01/rep_07'
sys.path[:0] = [str(SCRIPT), str(STAGE / 'src'),
                str(ROOT / 'stages/stage4_adaptive_control/src'),
                str(ROOT / 'stages/stage3_full3d/src')]

from baseline_acceptance_v2 import assess
from evaluate_execution_mode import evaluate
from baseline_accounting_v2 import task_wrench_cost


@pytest.fixture
def case_and_scoring():
    case_path = STAGE / 'configs/high_rom_v1/low_rom_regression_cases/balanced_ordinary_r01.json'
    case = json.loads(case_path.read_text())
    import hashlib
    scored_case = {'case_key': case['case_key'], 'physical_variant': case['cell']['family'],
                   'candidate': case.get('coordination_candidate', 'low_rom_registered'),
                   'path': str(case_path.relative_to(ROOT)),
                   'sha256': hashlib.sha256(case_path.read_bytes()).hexdigest()}
    scoring = json.loads((STAGE / 'docs/high_rom_v1/PHASE_B_MATRIX.json').read_text())['scoring']
    return case, scored_case, scoring


@pytest.fixture
def rep7(tmp_path):
    if not SOURCE.is_dir():
        pytest.skip('preserved V1 raw Rep 7 is unavailable on this host')
    for name in ('HIGH_ROM_CASE_RESULT.json', 'summary.json', 'runtime_artifacts.json',
                 'trace.npz', 'zero_value_waypoint_decisions.json'):
        os.link(SOURCE / name, tmp_path / name)
    return tmp_path


def replace_json(path, value):
    # Replace the hardlink rather than editing its inode, preserving V1 bytes.
    temp = path.with_name(path.name + '.new')
    temp.write_text(json.dumps(value))
    temp.replace(path)


def mutate_json(path, fn):
    value = json.loads(path.read_text())
    fn(value)
    replace_json(path, value)


def score_and_assess(path, case_and_scoring):
    case, scored_case, scoring = case_and_scoring
    mode = evaluate(path, scored_case, scoring,
                    goal_deg=case['task']['goal_deg'], start_deg=case['task']['start_deg'])
    summary = json.loads((path / 'summary.json').read_text())
    artifacts = json.loads((path / 'runtime_artifacts.json').read_text())
    with np.load(path / 'trace.npz') as trace:
        mask = trace['stage'] == 'TASK'
        costs = task_wrench_cost(trace, mask)
    decisions = json.loads((path / 'zero_value_waypoint_decisions.json').read_text())
    return mode, assess(summary, mode, artifacts, costs, decisions)


def test_a_real_long_wall_age_scientific_rep_continues(rep7, case_and_scoring):
    mode, baseline = score_and_assess(rep7, case_and_scoring)
    assert mode['raw_scorer_v2']['pass'] is False
    assert mode['raw_scorer_v2']['maximum_plan_activation_age_ms'] > 100
    assert mode['physical_task_result']['status'] == 'PASS'
    assert mode['scientific_validity']['status'] == 'PASS'
    assert baseline['overall_baseline_scientific_result'] == 'PASS'
    assert baseline['realtime_characterization']['counterfactual_realtime_validity'] == 'FAIL'
    assert baseline['gate_reasons'] == []


def test_b_scientific_version_mismatch_stops(rep7, case_and_scoring):
    def change(value):
        value['timing']['requests'][0]['receipt_simulation_version']['state_version'] += 1
    def change_artifacts(value):
        value['requests'][0]['receipt_simulation_version']['state_version'] += 1
    mutate_json(rep7 / 'summary.json', change)
    mutate_json(rep7 / 'runtime_artifacts.json', change_artifacts)
    mode, baseline = score_and_assess(rep7, case_and_scoring)
    assert mode['scientific_validity']['status'] == 'FAIL'
    assert baseline['overall_baseline_scientific_result'] == 'FAIL'


def test_c_physical_safety_failure_stops(rep7, case_and_scoring):
    mutate_json(rep7 / 'summary.json', lambda x: x['task'].__setitem__('peak_force_n', 1e6))
    mode, baseline = score_and_assess(rep7, case_and_scoring)
    assert mode['raw_scorer_v2']['conditions']['force'] is False
    assert mode['physical_task_result']['status'] == 'FAIL'
    assert baseline['overall_baseline_scientific_result'] == 'FAIL'


def test_d_non_wall_terminal_scorer_failure_stops(rep7, case_and_scoring):
    mutate_json(rep7 / 'summary.json', lambda x: x.__setitem__('status', 'INCOMPLETE'))
    mode, baseline = score_and_assess(rep7, case_and_scoring)
    assert mode['raw_scorer_v2']['conditions']['summary_complete'] is False
    assert baseline['overall_baseline_scientific_result'] == 'FAIL'


def test_e_realtime_stale_rule_remains_failure(rep7, case_and_scoring):
    mode_name = 'REALTIME_CHARACTERIZATION'
    mutate_json(rep7 / 'HIGH_ROM_CASE_RESULT.json',
                lambda x: x.__setitem__('execution_mode', mode_name))
    def change_summary(x):
        x['execution_mode'] = mode_name
        for request in x['timing']['requests']:
            request['execution_mode'] = mode_name
    def change_artifacts(x):
        x['execution_mode'] = mode_name
        for request in x['requests']:
            request['execution_mode'] = mode_name
    mutate_json(rep7 / 'summary.json', change_summary)
    mutate_json(rep7 / 'runtime_artifacts.json', change_artifacts)
    mode, baseline = score_and_assess(rep7, case_and_scoring)
    assert mode['raw_scorer_v2']['conditions']['plan_age'] is False
    assert mode['realtime_execution_validity']['status'] == 'FAIL'
    assert baseline['overall_baseline_scientific_result'] == 'FAIL'


def test_f_mode_mismatch_is_not_guessed(rep7, case_and_scoring):
    mutate_json(rep7 / 'summary.json',
                lambda x: x.__setitem__('execution_mode', 'REALTIME_CHARACTERIZATION'))
    with pytest.raises(ValueError, match='execution_mode'):
        score_and_assess(rep7, case_and_scoring)
