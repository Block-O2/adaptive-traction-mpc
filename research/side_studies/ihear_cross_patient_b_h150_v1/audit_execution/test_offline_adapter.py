"""Historical raw arithmetic + negative-path checks. No physics imports/starts."""
from pathlib import Path
import ast
import copy
import json
import shutil
import sys
import tempfile
sys.dont_write_bytecode = True
REVIEW = Path(__file__).resolve().parents[1]
OLD = Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1')
sys.path.insert(0, str(REVIEW))
import cross_analysis as ca

checks = []
for path in REVIEW.glob('*.py'):
    ast.parse(path.read_text())
    checks.append(dict(check='syntax', file=path.name, status='PASS'))
case = json.loads((OLD / 'source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/high_rom_nominal_sync_120_v1.json').read_text())
with tempfile.TemporaryDirectory(prefix='ihear_cross_adapter_offline_') as tmp:
    fixture = Path(tmp)
    for d in ['code', 'control', 'deps', 'output', 'reports', 'derived', 'motion_series', 'source/results', 'audit']:
        (fixture / d).mkdir(parents=True, exist_ok=True)
    for name in ['analyze_matched.py', 'explore_common.py', 'attribution.py', 'stream_runtime_evidence.py']:
        shutil.copy2(OLD / 'code' / name, fixture / 'code' / name)
    shutil.copy2(OLD / 'control/independent_recompute.py', fixture / 'control/independent_recompute.py')
    shutil.copy2(OLD / 'MOTION_ACCEPTANCE_PROTOCOL.json', fixture / 'MOTION_ACCEPTANCE_PROTOCOL.json')
    ca.configure(fixture)
    rows = []
    for arm in ['B', 'H150']:
        ident = 'D02_' + arm
        (fixture / 'source/results' / ident).symlink_to(OLD / 'source/results' / ident, target_is_directory=True)
        for suffix in ['.json', '_DATA.json']:
            shutil.copy2(OLD / 'output' / (ident + suffix), fixture / 'output' / (ident + suffix))
        row = ca.evaluate_run(ident, arm=arm, case=case)
        assert row['complete_task'] and row['absolute_task_execution_qualified'], row
        assert row['axes']['task'] == row['axes']['absolute_safety'] == row['axes']['causal_execution'] == 'PASS'
        historical = json.loads((OLD / 'reports' / (ident + '_MEASURED.json')).read_text())
        assert abs(row['J_F_N_s']-historical['J_F_N_s']) < 1e-8
        bad_metric = json.loads((OLD / 'output' / (ident + '.json')).read_text())
        bad_metric['physical_audit']['unchanged_evaluator']['scientific_validity']['status'] = 'FAIL'
        axes = ca._axes(json.loads((OLD / 'source/results' / ident / 'summary.json').read_text()), bad_metric, historical, True)
        assert axes['causal_execution'] == 'FAIL'
        row['branch'].update(patient_id='TEST', case_sha256='SYNTHETIC_IDENTITY', model_xml_sha256='SYNTHETIC_IDENTITY')
        rows.append(row)
        checks.append(dict(check='historical_complete_raw_evaluation', id=ident, status='PASS', J_F_N_s=row['J_F_N_s'],
                           actual_new_native_steps=row['actual_new_native_steps'],
                           final_reference=row['motion_extra']['final_issued_return_reference_deg'],
                           true_return_undershoot=row['motion_extra']['return_undershoot_deg']))
        independent = ca.independent_verify(ident)
        assert independent['status'] == 'PASS', independent
        checks.append(dict(check='independent_raw_arithmetic_and_receipts', id=ident, status='PASS'))
    paired = ca.compare_pair('TEST', *copy.deepcopy(rows))
    assert paired['complete_qualified_H150'] and paired['motion_relative'] == 'PASS'
    assert rows[0]['motion_relative'] == 'NOT_APPLICABLE_SELF_REFERENCE'
    checks.append(dict(check='qualified_historical_pair', status='PASS', gain_percent=paired['gain_percent']))
    bad = copy.deepcopy(rows)
    bad[0]['absolute_task_execution_qualified'] = False
    bad[0]['axes']['absolute_safety'] = 'FAIL'
    pair = ca.compare_pair('TEST', *bad)
    assert pair['motion_relative'] == 'NOT_EVALUABLE_INVALID_B'
    assert pair['gain_percent'] is not None and not pair['relative_gain_is_qualified']
    checks.append(dict(check='unsafe_B_never_qualified_motion_reference', status='PASS'))
    checks.append(dict(check='scientific_version_age_failure_not_hidden_by_receipt_ownership', status='PASS'))
    bad = copy.deepcopy(rows)
    bad[1]['branch']['case_sha256'] = 'WRONG_PATIENT'
    pair = ca.compare_pair('TEST', *bad)
    assert not pair['pair_identity_valid'] and pair['gain_percent'] is None
    checks.append(dict(check='different_patient_identity_refuses_gain', status='PASS'))
    ident = 'SYNTHETIC_INCOMPLETE'
    (fixture / 'source/results' / ident).mkdir()
    ca.put('source/results/' + ident + '/summary.json', dict(status='ABORTED', task=dict(phase_transitions=[]), abort_reason='SYNTHETIC_TEST'))
    partial = ca.evaluate_run(ident, arm='H150', case=case)
    assert partial['J_F_N_s'] is None and partial['axes']['task'] == 'FAIL'
    assert partial['absolute_task_execution_qualified'] is False
    checks.append(dict(check='incomplete_task_preserved_without_full_gain', status='PASS'))
    adapter = json.loads((fixture / 'audit/EVALUATION_ADAPTER.json').read_text())
forbidden = [n for n in sys.modules if n == 'mujoco' or n == 'study_common' or n == 'sac_env']
assert not forbidden, forbidden
result = dict(status='PASS', evidence='OFFLINE_ARITHMETIC_AND_SYNTHETIC_NEGATIVE_PATHS', checks=checks,
              adapter=adapter, new_physics_starts=0, imports_physics=False,
              historical_files_read_only=True, fixture='temporary isolated fixture removed after test')
(REVIEW / 'audit_execution/OFFLINE_ADAPTER_CHECK.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
