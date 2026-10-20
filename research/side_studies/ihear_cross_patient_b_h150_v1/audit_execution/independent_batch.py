"""Independent offline checking of fully joined patient processes; no physics.

Run from the review tree against canonical results. Never imports runners or
controllers. Frozen execution files are read-only. This script is not part of
the execution manifest and may only write its new audit/derived checks.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import time

sys.dont_write_bytecode = True
P = Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
sys.path.insert(0, str(P))
import cross_analysis as ca
ca.configure(P)


def read(rel, default=None):
    path = P / rel
    return json.loads(path.read_text()) if path.exists() else default


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def put(rel, data):
    path = P / rel
    assert path.parts[:len(P.parts)] == P.parts
    assert path.relative_to(P).parts[0] in ('audit', 'derived')
    assert not path.exists(), 'PRESERVE_EXISTING_AUDIT:' + str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(ca.clean(data), indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    temp.replace(path)


def review(pid):
    done = read(pid+'_DONE.json')
    owner = read('audit/'+pid+'_OWNER.json')
    exit_record = read(pid+'_WORKER_EXIT.json')
    if not done or not owner or not owner.get('joined') or not exit_record:
        return dict(patient_id=pid, status='WAITING_FOR_JOINED_PROCESS')
    assert exit_record.get('active_child') is None, 'UNJOINED_PATIENT_CHILD'
    output = 'audit/INDEPENDENT_COMPLETE_'+pid+'.json'
    if (P/output).exists():
        prior = read(output)
        return dict(patient_id=pid, status=prior['status'], already_verified=True)
    plan = read(pid+'_PLAN.json'); patient = plan['patient']
    case_path = P / patient['case_path']; case_hash = sha(case_path)
    static = read('patients/'+pid+'/static/MODEL_STATIC_AUDIT.json')
    identity = read('audit/'+pid+'_RUNTIME_MODEL_IDENTITY.json', {})
    binding = read('audit/'+pid+'_PATIENT_EVALUATOR_BINDING.json', {})
    check = dict(case_file_hash=case_hash == patient['case_sha256'],
                 static_xml_hash=sha(P/'patients'/pid/'static/model.xml') == static['xml_sha256'],
                 runtime_physical_model_matches_static=identity.get('physical_human') == static['human_dataclass'],
                 runtime_prior_is_frozen=identity.get('control_prior_source') == 'FROZEN_HIGH_ROM_DEPLOYABLE_PRIOR_NOT_PATIENT_TRUTH',
                 runtime_case_hash=identity.get('case_sha256') == case_hash,
                 runtime_xml_hash=identity.get('xml_sha256') == static['xml_sha256'],
                 metadata_case_path=binding.get('case_path') == str(case_path),
                 metadata_case_hash=binding.get('case_sha256') == case_hash,
                 evaluator_controller_unchanged=binding.get('controller_changed') is False,
                 evaluator_thresholds_unchanged=binding.get('scoring_formula_or_threshold_changed') is False)
    if not identity:
        for key in ['runtime_physical_model_matches_static','runtime_prior_is_frozen','runtime_case_hash','runtime_xml_hash']:
            check[key] = None
    if not binding:
        for key in ['metadata_case_path','metadata_case_hash','evaluator_controller_unchanged','evaluator_thresholds_unchanged']:
            check[key] = None
    manifest = read('EXECUTION_CODE_MANIFEST.json')
    important = ['cross_runner.py', 'cross_analysis.py', 'code/study_common.py', 'code/analyze_matched.py',
                 'code/explore_common.py', 'control/campaign_v2.py', 'control/independent_recompute.py']
    source_check = {rel: sha(P/rel) == manifest['files'][rel] for rel in important}
    attempts = [json.loads(line) for line in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
    starts = [r for r in attempts if r['event'] == 'START' and r['id'].startswith(pid+'_')]
    ends = [r for r in attempts if r['event'] == 'END' and r['id'].startswith(pid+'_')]
    accounting = dict(start_ids=sorted(r['id'] for r in starts), end_ids=sorted(r['id'] for r in ends),
                      every_start_ended=sorted(r['id'] for r in starts) == sorted(r['id'] for r in ends),
                      starts_use_frozen_manifest=all(r['source_sha256'] == sha(P/'EXECUTION_CODE_MANIFEST.json') for r in starts),
                      starts_use_actual_case=all(r['case_sha256'] == case_hash for r in starts),
                      every_end_joined=all(r.get('joined') is True for r in ends))
    rows = []
    for arm in ('B', 'H150', 'parent'):
        ident = pid+'_'+arm
        evaluation = read('reports/'+ident+'_CROSS_EVALUATION.json', {})
        if not evaluation.get('complete_task') or evaluation.get('integration') != 'PASS':
            rows.append(dict(id=ident, status='PARTIAL_OR_UNVERIFIABLE_PRESERVED',
                             complete_task=evaluation.get('complete_task'),
                             reported_axes=evaluation.get('axes'), J_F_N_s=evaluation.get('J_F_N_s')))
            continue
        launch = read('source/results/'+ident+'/HIGH_ROM_CASE_RESULT.json')
        summary = read('source/results/'+ident+'/summary.json')
        measured = read('reports/'+ident+'_MEASURED.json')
        original = measured['native_physical_audit']['unchanged_evaluator']
        row_checks = dict(launch_uses_actual_case=launch['case_sha256'] == case_hash,
                          scorer_uses_actual_case=original['raw_scorer_v2']['registered_case_sha256'] == case_hash,
                          mode_consistent=launch['execution_mode'] == summary['execution_mode'] == original['execution_mode'] == 'SCIENTIFIC_SIMULATION',
                          physical_safety_separate='absolute_safety_checks' in evaluation['axes'],
                          no_B_self_motion_claim=arm not in ('B', 'parent') or evaluation['motion_relative'] == 'NOT_APPLICABLE_SELF_REFERENCE')
        marker = P / 'derived' / (ident+'_INDEPENDENT.json')
        if marker.exists():
            independent = json.loads(marker.read_text())
            assert independent['status'] == 'PASS'
            # Existing audits are immutable; confirm the same raw inputs remain.
            assert all(sha(Path(path)) == digest for path, digest in measured['sources'].items())
        else:
            independent = ca.independent_verify(ident)
        rows.append(dict(id=ident, status='PASS' if independent['status'] == 'PASS' and all(row_checks.values()) else 'FAIL',
                         identity_checks=row_checks, raw_independent=independent,
                         reported_axes={k:evaluation['axes'][k] for k in ['task','absolute_safety','causal_execution']},
                         reported_qualification=evaluation['qualification'],
                         source_case_hash=case_hash, branch=evaluation.get('branch')))
        print('INDEPENDENT_ARM', ident, rows[-1]['status'], flush=True)
    b = next((r for r in rows if r['id'] == pid+'_B'), {})
    h = next((r for r in rows if r['id'] == pid+'_H150'), {})
    paired = read('reports/'+pid+'_PAIR_ANALYSIS.json', {})
    pair_check = None
    if b.get('branch') and h.get('branch'):
        pair_check = dict(matched_full_state=b['branch']['full_hash'] == h['branch']['full_hash'],
                          same_patient=b['branch']['patient_id'] == h['branch']['patient_id'] == pid,
                          actual_case=b['branch']['case_sha256'] == h['branch']['case_sha256'] == case_hash,
                          actual_model=b['branch']['model_xml_sha256'] == h['branch']['model_xml_sha256'] == static['xml_sha256'],
                          reported_pair_valid=paired.get('pair_identity_valid') is True)
    failures = (any(value is False for value in check.values()) or not all(source_check.values()) or
                not all(accounting[k] for k in ['every_start_ended','starts_use_frozen_manifest','starts_use_actual_case','every_end_joined']) or
                any(r['status'] == 'FAIL' for r in rows) or (pair_check is not None and not all(pair_check.values())))
    status = 'FAIL' if failures else 'PASS' if all(r['status'] == 'PASS' for r in rows) and all(check.values()) else 'PARTIAL_PRESERVED'
    result = dict(patient_id=pid, status=status, unix=time.time(), reviewer_pid=os.getpid(),
                  origin='Independent offline auditor process after owned patient join',
                  model_and_evaluator_identity=check, frozen_sources=source_check, accounting=accounting,
                  pair_identity=pair_check, rows=rows, new_physics_starts=0, imports_physics=False)
    forbidden = [name for name in sys.modules if name == 'mujoco' or name in ('study_common','cross_runner','sac_env')]
    assert not forbidden, forbidden
    put(output, result)
    review_path = Path(read('ENVIRONMENT.json')['review']) / output
    review_path.parent.mkdir(parents=True, exist_ok=True)
    if not review_path.exists(): review_path.write_text(json.dumps(ca.clean(result), indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    return result


if __name__ == '__main__':
    watching = '--watch' in sys.argv[1:]
    requested = [x for x in sys.argv[1:] if x != '--watch'] or read('VIRTUAL_PATIENT_COHORT.json')['order']
    if watching:
        print('OFFLINE_AUDITOR_STARTED', os.getpid(), flush=True)
        reported = {}
        while time.time() < read('RUN_PLAN.json')['hard_stop_unix']:
            for pid in requested:
                result = review(pid)
                if result['status'] != 'WAITING_FOR_JOINED_PROCESS' and reported.get(pid) != result['status']:
                    reported[pid] = result['status']
                    print('OFFLINE_PATIENT', pid, result['status'], flush=True)
            active = read('OWNED_ACTIVE_PROCESS.json', {})
            ended = (P/'SERIAL_CAMPAIGN_DONE.json').exists() or (P/'PHYSICS_STOP.json').exists()
            if ended and active.get('status') == 'IDLE':
                break
            time.sleep(30)
        print('OFFLINE_AUDITOR_STOPPED', os.getpid(), json.dumps(reported), flush=True)
    else:
        result = [review(pid) for pid in requested]
        print(json.dumps([dict(patient_id=r['patient_id'],status=r['status']) for r in result]), flush=True)
