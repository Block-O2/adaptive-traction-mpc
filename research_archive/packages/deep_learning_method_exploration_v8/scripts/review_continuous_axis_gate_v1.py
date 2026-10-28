"""Review closed original Gate1 evidence. No actor/model imports or physics."""
from pathlib import Path
import hashlib, json, os, time

P = Path(__file__).resolve().parents[1]
G = 'V8AXISG01'
HARD = ['force', 'moment', 'torque', 'human_speed', 'human_acceleration', 'robot_speed',
        'session_clearance', 'true_clearance', 'measured_sleeve_clearance',
        'no_shank_table_contact', 'no_human_rom_violation']
evidence = {}

def read(relative):
    path = P / relative
    evidence[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())

def new(relative, value):
    with (P / relative).open('x') as f:
        json.dump(value, f, indent=2, allow_nan=False, ensure_ascii=False)
        f.write('\n')

config = read('experiments/' + G + '.json')
manifest = read('jobs/' + G + '/SOURCE_MANIFEST.json')
assert manifest['config_sha256'] == evidence['experiments/' + G + '.json']
for rel, expected in config['frozen_artifacts'].items():
    path = P / rel
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, rel
    evidence[rel] = expected
end = read('owned/' + G + '_SUPERVISOR_END.json')
done = read('jobs/' + G + '/WORKER_DONE.json')
assert end['state'] == 'STOP' and end['worker_exit_code'] == 0 and not end['survivors']
assert done['all_children_joined'] and done['status'] == 'PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS'
assert all(r['unchanged'] and r['child_exitcode'] == 0 for r in done['parent_checks'])
for pid, old in end['known_owned'].items():
    proc = Path('/proc') / pid / 'stat'
    if proc.exists():
        parts = proc.read_text().rsplit(')', 1)[1].split()
        assert int(parts[19]) != old['start_ticks'] or parts[0] == 'Z'
assert read('audit/' + G + '_PARENT_RAW_GATE.json')['status'] == 'PASS'
repeat = read('audit/' + G + '_AXIS_L1_REPEAT_GATE.json')
assert repeat['status'] == 'PASS'
assert Path(repeat['a']).resolve() == P / 'runtime/source/results' / (G + '_H150')
assert Path(repeat['b']).resolve() == P / 'runtime/source/results' / (G + '_AXIS_L1')
tags = ['parent', 'B', 'H150', 'AXIS_L1', 'AXIS_L0', 'AXIS_L05']
ids = {G + '_' + tag for tag in tags}
events = {}
for raw in (P / 'runtime/ATTEMPTS.jsonl').read_bytes().splitlines():
    row = json.loads(raw)
    if row.get('id') in ids and row['event'] in ('START', 'END'):
        key = row['id'] + '|' + row['event']
        assert key not in events
        events[key] = dict(record=row, raw_line_without_newline_sha256=hashlib.sha256(raw).hexdigest())
assert len(events) == 12
rows = {}
for tag in tags:
    ident = G + '_' + tag
    event_end = events[ident + '|END']['record']
    assert event_end['joined'] and event_end['returncode'] == 0
    if tag != 'parent':
        assert event_end['parent_hash_equal'] is True
    metrics = read('runtime/reports/' + ident + '_MEASURED.json')
    physical = metrics['native_physical_audit']
    common = physical['unchanged_evaluator']['physical_task_result']['scorer_v2_common_conditions']
    assert physical['pass_'] and all(common.get(k) is True for k in HARD)
    assert metrics['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID'] == 'PASS'
    assert read('audit/scorer_replay/' + ident + '.json')['status'] == 'SCORER_REPLAY_PASS'
    if tag == 'parent':
        continue
    result = read('attempts/' + ident + '_RESULT.json')
    assert result['complete'] and result['error'] is None
    line_path = Path(metrics['execution_lineage_path']).resolve()
    assert line_path.is_relative_to(P)
    lineage = read(str(line_path.relative_to(P)))
    assert lineage['status'] == 'PASS' and lineage['ownership_error_count'] == 0
    assert any(r.get('selected_plan_activated') is True and r.get('actual_native_steps', 0) > 0 for r in lineage['rows'])
    read('attempts/' + ident + '_EXECUTION_BINDING.json')
    rows[tag] = {key:result[key] for key in ['complete', 'qualified', 'JF', 'JM', 'actual_new_native_steps']}
    rows[tag]['failed_requirements'] = result['motion_vs_B']['failed_requirements']
assert all(rows[tag]['qualified'] for tag in ['B', 'H150', 'AXIS_L1', 'AXIS_L05'])
assert rows['H150']['JF'] == rows['AXIS_L1']['JF'] and rows['H150']['JM'] == rows['AXIS_L1']['JM']
assert not rows['AXIS_L0']['qualified'] and rows['AXIS_L0']['failed_requirements'] == ['acceleration_deg_s2/p95_abs']
for rel, expected in evidence.items():
    assert hashlib.sha256((P / rel).read_bytes()).hexdigest() == expected
review = dict(schema='v8.beta_axis_gate1_main_review.v1',
              status='PASS_ENGINEERING_MAPPING_REVIEWED_FOR_REAL_SAMPLING', reviewed_unix=time.time(),
              group=G, axis_object_sha256=config['continuous_axis_gate1']['axis_object_sha256'],
              lambda1_original_H150_exact_raw_PASS=True, original_B_full_qualified=True,
              original_H150_full_qualified=True, lambda0_and_lambda05_engineering_review_completed=True,
              mean_lambda05_full_original_qualified=True, true_hard_safety_violation=False,
              original_evidence_files_sha256=evidence, original_event_records_and_hash_scopes=events,
              rows=rows, lambda0_failed_original_motion_preserved=True,
              same_axis_domain_retained=[0., 1.], domain_narrowed_after_outcomes=False,
              original_global_stop_unix=1793114740., real_Beta_initialization_authorized_by_this_review=False,
              real_Beta_sampling_authorized_by_this_review=False, real_Beta_update_authorized_by_this_review=False,
              limits='Known-heavy exposed engineering only; does not establish full-axis qualification, new-condition ability, or learning/control superiority.',
              new_model_forward=0, new_fit=0, new_physics=0,
              reviewer_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
new('audit/CONTINUOUS_AXIS_GATE1_MAIN_REVIEW_V1.json', review)
print('GATE1_MAIN_REVIEW_PASS', 'lambda0 original motion fail preserved', 'mean .5 qualified', 'zero Beta calls')
