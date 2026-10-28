"""Finite evaluation-only consolidation; never executes a controller or model."""
from pathlib import Path
import csv
import hashlib
import json
import sys
import time

P = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(group, tag):
    f = P / 'analysis/native_metrics' / (group + '_' + tag + '.json')
    return read(f) if f.exists() else None


def put(path, data):
    assert not path.exists(), 'REFUSE_OVERWRITE:' + str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    t = path.with_name(path.name + '.tmp')
    t.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    t.replace(path)


destination = P / sys.argv[1]
assert not destination.exists(), 'NEW_OUTPUT_DIRECTORY_REQUIRED'
destination.mkdir(parents=True)
inputs = {}
rows = []
paired = []
for config_file in sorted((P / 'experiments').glob('*.json')):
    c = read(config_file)
    group = c['group']
    if not (P / 'owned' / (group + '_SUPERVISOR_END.json')).exists():
        continue
    inputs[str(config_file.relative_to(P))] = sha(config_file)
    reference_tag = 'LATE_PHASE' if group.startswith('CFACTOR') else 'V6PHASE'
    reference = metrics(group, reference_tag)
    freeze_file = P / 'freeze' / (group + '.json')
    freeze = read(freeze_file)
    inputs[str(freeze_file.relative_to(P))] = sha(freeze_file)
    bounds = freeze.get('quality_contract', {})
    group_pairs = []
    for f in sorted((P / 'attempts').glob(group + '_*_RESULT.json')):
        r = read(f)
        inputs[str(f.relative_to(P))] = sha(f)
        ident = r['id']
        tag = ident[len(group) + 1:]
        m = metrics(group, tag)
        if m:
            mf = P / 'analysis/native_metrics' / (ident + '.json')
            inputs[str(mf.relative_to(P))] = sha(mf)
        row = {
            'id': ident, 'group': group, 'tag': tag,
            'case_path': c.get('case_path'), 'case_sha256': c.get('case_sha256'),
            'fork_phase': c.get('fork_phase'), 'fork_slot': c.get('fork_slot'),
            'delayed_until_OUT1': bool(r.get('action', {}).get('original_B_through_outbound_slots')),
            'complete': bool(r.get('complete')), 'original_qualified': bool(r.get('qualified')),
            'successful_cost_rank_eligible': bool(r.get('complete') and r.get('qualified')),
            'JF': r.get('JF'), 'JM': r.get('JM'), 'error': r.get('error'),
            'failed_original_gates': r.get('failed'),
            'partial_evidence_unranked': r.get('protected_task_failure'),
            'full_native_metrics': m,
        }
        rows.append(row)
        if reference and m:
            ratios = [a / b for a, b in zip(m['native_motion']['jerk_deg_s3']['rms'], reference['native_motion']['jerk_deg_s3']['rms'])]
            ratios.append(m['native_force']['norm_rate']['rms'] / reference['native_force']['norm_rate']['rms'])
            j = bounds.get('hip_knee_jerk_RMS_ratio_max_vs_V6PHASE')
            w = bounds.get('force_norm_rate_RMS_ratio_max_vs_V6PHASE')
            retain = all(v <= b for v, b in zip(ratios, [j, j, w])) if j is not None and w is not None else None
            group_pairs.append({
                'id': ident, 'reference_id': reference['id'],
                'candidate_original_qualified': bool(r.get('qualified')),
                'reference_original_qualified': reference['qualified_original'],
                'JF': m['JF'], 'JM': m['JM'],
                'delta_JF': m['JF'] - reference['JF'], 'delta_JM': m['JM'] - reference['JM'],
                'hip_knee_jerk_force_rate_ratios': ratios, 'extra_quality_retained': retain,
                'both_cost_improvement_and_quality': bool(r.get('qualified') and reference['qualified_original'] and retain and m['JF'] < reference['JF'] and m['JM'] <= reference['JM']),
            })
    paired.append({'group': group, 'reference_tag': reference_tag,
                   'reference_complete': reference is not None,
                   'reference_original_qualified': reference['qualified_original'] if reference else None,
                   'quality_bounds': bounds, 'rows': group_pairs,
                   'missing_reference_means': 'NOT_EVALUABLE, never default pass',
                   'unqualified_complete_reference_means': 'Continuous ratios diagnostic only; formal success false'})

csv_rows = []
for r in rows:
    m = r['full_native_metrics']
    z = {k: r[k] for k in ['id', 'group', 'tag', 'complete', 'original_qualified', 'successful_cost_rank_eligible', 'JF', 'JM', 'error', 'delayed_until_OUT1']}
    z['partial_JF_unranked'] = (r['partial_evidence_unranked'] or {}).get('partial_JF_unranked')
    for axis, name in enumerate(['hip', 'knee']):
        for variable in ['velocity_deg_s', 'acceleration_deg_s2', 'jerk_deg_s3']:
            for stat in ['rms', 'peak_abs', 'p95_abs', 'p99_abs']:
                z[name + '_' + variable + '_' + stat] = m['native_motion'][variable][stat][axis] if m else None
    for kind in ['force', 'moment']:
        for stat in ['rms', 'peak_abs', 'p95_abs', 'p99_abs']:
            z[kind + '_norm_rate_' + stat] = m['native_' + kind]['norm_rate'][stat] if m else None
        z[kind + '_vector_TV'] = m['native_' + kind]['TV_vector'] if m else None
        z[kind + '_norm_TV'] = m['native_' + kind]['TV_norm'] if m else None
    for name in ['tracking_RMS_deg', 'excursion_deg', 'endpoint_deg', 'clearance', 'axes', 'native_torque', 'guard', 'original_motion_comparison']:
        z[name] = json.dumps(m[name], sort_keys=True) if m else None
    csv_rows.append(z)
with (destination / 'ALL_CANDIDATE_METRICS.csv').open('x', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(csv_rows[0]) if csv_rows else ['id'])
    writer.writeheader()
    writer.writerows(csv_rows)
put(destination / 'ALL_CANDIDATE_EVIDENCE.json', {'schema': 'ihear.final_evidence.v1', 'created_unix': time.time(), 'rows': rows, 'scope': 'All ended groups; no cross-Human or cross-permission cost ranking; complete failures and partials retained.'})
put(destination / 'FROZEN_QUALITY_PAIRS.json', {'groups': paired, 'evaluation_only': True, 'thresholds_unchanged': True})
for rel, expected in inputs.items():
    assert sha(P / rel) == expected, 'INPUT_CHANGED:' + rel
put(destination / 'INPUT_MANIFEST.json', {'source_sha256': sha(Path(__file__)), 'input_sha256': inputs, 'new_env_physics_model_training': 0})
print('FINAL_EVIDENCE_TABLES', len(rows), 'rows', len(paired), 'ended groups', flush=True)
