"""Read-only historical decision audit; outputs only under this family dir."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD = ROOT / 'rl_b_matched_recovery_stability_v1/github/research/side_studies/ihear_history_to_next_trial_learning_v1'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    manifest = []
    rows = []
    for patient in ['V12', 'U14', 'U15', 'U16']:
        file = OLD / ('learning/' + patient + '_T2_DECISIONS_FROZEN.json')
        manifest.append(dict(path=str(file), sha256=sha(file), bytes=file.stat().st_size))
        data = json.loads(file.read_text())
        decisions = {d['method']: d for d in data['decisions']}
        for method in ['BO', 'VALUE']:
            enabled = decisions[method]; disabled = decisions[method + '_DISABLED']
            def cost_relative(d):
                c = [p['predicted_cost_delta_from_trial1_N_s'] for p in d['predictions']]
                return [v - c[0] for v in c]
            er = cost_relative(enabled); dr = cost_relative(disabled)
            raw_best = min(range(len(er)), key=lambda i: er[i])
            rows.append(dict(patient=patient, method=method,
                actual_selected_index=enabled['selected_index'], disabled_selected_index=disabled['selected_index'],
                selected_action_changed_by_history=enabled['action']['action_hash'] != disabled['action']['action_hash'],
                enabled_action_relative_predictions_N_s=er, disabled_action_relative_predictions_N_s=dr,
                largest_history_effect_on_action_advantage_N_s=max(abs(e-d) for e,d in zip(er,dr)),
                enabled_unconstrained_mean_best_index=raw_best,
                enabled_eligible=[p['eligible'] for p in enabled['predictions']],
                prediction_only=True, physical_benefit_independently_recomputed=False,
                original_model_sha256=enabled['model_sha256']))
    mandatory = ['models/history_models.npz', 'models/TRAINING_DATA.json',
                 'models/POPULATION_HISTORY.json', 'LEARNING_RESULTS.json',
                 'ATTEMPT_ACCOUNTING.json', 'PACKAGE_VERIFICATION.json',
                 'learning/V12_T1_RAW_HISTORY.json', 'learning/V12_T1_HISTORY.json']
    availability = {name: (OLD/name).exists() for name in mandatory}
    for name in ['REPORT.md','history_features.py','learning_models.py','train_models.py',
                 'continuous_runner.py','ACTION_SPACE_CONTRACT.md','models/METHOD_FREEZE.json']:
        file=OLD/name;manifest.append(dict(path=str(file),sha256=sha(file),bytes=file.stat().st_size))
    report = dict(scope='OFFLINE_READ_ONLY_FROZEN_DECISION_AUDIT',
                  no_training=True, no_physics=True, training_rows_added=0,
                  physical_attempts=0, rows=rows, expected_assets_present=availability,
                  historical_performance_level='SUPPORTED_REPORT_ONLY_NOT_RAW_RECOMPUTED',
                  report_does_not_establish_control_increment=True)
    for name, value in [('HISTORICAL_DECISION_DIAGNOSTIC.json', report),
                        ('HISTORICAL_SOURCE_MANIFEST.json', dict(files=manifest))]:
        destination=HERE/name
        if destination.exists():
            raise FileExistsError('PRESERVE_EXISTING_ANALYSIS:'+str(destination))
        destination.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps(dict(rows=len(rows),physical_attempts=0,training_runs=0,
                         available_required_assets=sum(availability.values())),ensure_ascii=False))


if __name__ == '__main__':
    main()
