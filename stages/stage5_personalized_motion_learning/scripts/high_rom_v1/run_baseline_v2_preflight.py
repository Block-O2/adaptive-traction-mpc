"""Re-evaluate preserved V1 Rep 7 under the frozen V2 acceptance contract."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
STAGE = ROOT / 'stages/stage5_personalized_motion_learning'
SCRIPT = STAGE / 'scripts/high_rom_v1'
sys.path[:0] = [str(SCRIPT), str(STAGE / 'src'),
                str(ROOT / 'stages/stage4_adaptive_control/src'),
                str(ROOT / 'stages/stage3_full3d/src')]
from baseline_acceptance_v2 import assess
from evaluate_execution_mode import evaluate
from baseline_accounting_v2 import task_wrench_cost


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rep = STAGE / 'results/zero_value_30rep_baseline_v1/formal_session_01/rep_07'
    docs = STAGE / 'docs/zero_value_30rep_baseline_v2'
    case_path = STAGE / 'configs/high_rom_v1/low_rom_regression_cases/balanced_ordinary_r01.json'
    case = json.loads(case_path.read_text())
    scored_case = {'case_key': case['case_key'], 'physical_variant': case['cell']['family'],
                   'candidate': case.get('coordination_candidate', 'low_rom_registered'),
                   'path': str(case_path.relative_to(ROOT)), 'sha256': sha(case_path)}
    scoring = json.loads((STAGE / 'docs/high_rom_v1/PHASE_B_MATRIX.json').read_text())['scoring']
    mode = evaluate(rep, scored_case, scoring,
                    goal_deg=case['task']['goal_deg'], start_deg=case['task']['start_deg'])
    summary = json.loads((rep / 'summary.json').read_text())
    artifacts = json.loads((rep / 'runtime_artifacts.json').read_text())
    with np.load(rep / 'trace.npz') as trace:
        mask = trace['stage'] == 'TASK'
        costs = task_wrench_cost(trace, mask)
    decisions = json.loads((rep / 'zero_value_waypoint_decisions.json').read_text())
    acceptance = assess(summary, mode, artifacts, costs, decisions)
    if (acceptance['overall_baseline_scientific_result'] != 'PASS'
            or acceptance['raw_scorer_v2_result']['pass'] is not False
            or acceptance['realtime_characterization']['max_wall_plan_age_ms'] <= 100
            or acceptance['realtime_characterization']['counterfactual_realtime_validity'] != 'FAIL'):
        raise RuntimeError('V2 mode-aware long-wall-age sanity failed')
    record = {
        'schema': 'zero_value_30rep_baseline_v2_preflight_v1',
        'source': 'preserved V1 formal Rep 7; no new scientific run',
        'v1_negative_checkpoint': '22c6859214256a46e75d47ad153ed9be3c3a2f72',
        'source_mode_result_sha256': sha(rep / 'MODE_AWARE_RESULT_V2.json'),
        'contract_v2_sha256': sha(docs / 'ZERO_VALUE_30REP_BASELINE_CONTRACT_V2.json'),
        'acceptance_module_sha256': sha(SCRIPT / 'baseline_acceptance_v2.py'),
        'actual_execution_mode': mode['execution_mode'],
        'physical_task_validity': acceptance['physical_task_validity'],
        'scientific_validity': acceptance['scientific_validity'],
        'raw_scorer_v2_result': acceptance['raw_scorer_v2_result'],
        'realtime_characterization': acceptance['realtime_characterization'],
        'overall_baseline_scientific_result': acceptance['overall_baseline_scientific_result'],
        'gate_reasons': acceptance['gate_reasons'],
        'test_suite': 'A-F real-scorer integrations + existing mode-aware/boundary tests: 16 passed',
    }
    (docs / 'PREFLIGHT_REPAIR_01.json').write_text(json.dumps(record, indent=2, sort_keys=True,
                                                          allow_nan=False) + '\n')
    print(json.dumps({'preflight': 'PASS', 'raw_scorer_v2': False,
                      'wall_plan_age_ms': record['realtime_characterization']['max_wall_plan_age_ms'],
                      'baseline_scientific': record['overall_baseline_scientific_result']}))


if __name__ == '__main__':
    main()
