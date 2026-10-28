"""Root-only metadata preflight for the two remaining preoutcome frozen jobs.
No preparation, model, scorer, mapping, or physics calls. Never changes configs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

P = Path(__file__).resolve().parents[1]
EXPECTED = {
    'V8FMEAN04': ('afe0d0773e02c0ee9f8c0d379bc013995dcb86c91986fef0a5097637e954c65f', 129, 'V8VAL04'),
    'V8CONVAL02': ('af16c44145d4ba204730b7b9e88b91620689ee2c6caff40ffd9f06185b9091a0', 2046, 'V8FMEAN04'),
}
MASTER = 'freeze/COMPLETE_MODEL_PROCEDURE_PREVALIDATION_MASTER_V1.json'
MASTER_SHA = 'b7e41810af973c4af2fa9287c6801f37ae4ca0cee923e65e754c578ac83f728e'
CASE_SHA = '224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87'


def sha(relative):
    target = (P / relative).resolve()
    assert target.is_relative_to(P)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def read(relative):
    return json.loads((P / relative).read_text())


def ref(relative):
    return dict(path=relative, sha256=sha(relative))


def current_ticks(pid):
    try:
        return int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=EXPECTED, required=True)
    args = parser.parse_args()
    group = args.group
    expected, pin_count, prior = EXPECTED[group]
    plan = read('runtime/RUN_PLAN.json')
    assert plan['hard_stop_unix'] == 1793114740.0
    assert plan['physics_hard_stop_unix'] == 1793112940.0
    assert plan['physical_timeout_s'] == 600 and plan['all_physics_serial'] is True
    assert time.time() < plan['dispatch_cutoff_unix'] - plan['physical_timeout_s']
    config_path = 'experiments/' + group + '.json'
    assert sha(config_path) == expected
    config = read(config_path)
    assert config['case_sha256'] == CASE_SHA == sha(config['case_path'])
    assert config['condition']['seed'] == 2026102754
    assert config['group'] == group and len(config['frozen_artifacts']) == pin_count
    assert not (P / 'jobs' / group).exists()
    assert not (P / 'owned' / ('JOB_' + group + '.lock')).exists()
    assert sha(MASTER) == MASTER_SHA
    master = read(MASTER)
    assert len(master['frozen_artifacts']) == 2042
    for relative, expected_sha in {**master['frozen_artifacts'], **config['frozen_artifacts']}.items():
        assert sha(relative) == expected_sha, relative
    starts, ends = {}, {}
    for raw in (P / 'runtime/ATTEMPTS.jsonl').read_bytes().splitlines():
        event = json.loads(raw)
        if event.get('event') not in ('START', 'END'):
            continue
        table = starts if event['event'] == 'START' else ends
        assert event['id'] not in table
        table[event['id']] = event
    assert starts.keys() == ends.keys()
    assert all(row.get('joined') is True for row in ends.values())
    owner_evidence = []
    for old_group in sorted({row['group'] for row in starts.values()}):
        ending = 'owned/' + old_group + '_SUPERVISOR_END.json'
        beginning = 'owned/' + old_group + '_SUPERVISOR.json'
        end, begin = read(ending), read(beginning)
        assert end['state'] == 'STOP' and end['survivors'] == []
        for owner in [begin['identity'], *end['known_owned'].values()]:
            assert current_ticks(owner['pid']) != owner['start_ticks'], owner
        owner_evidence.append(ref(ending))
    assert any(row['group'] == prior for row in starts.values())
    ram = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                   if line.startswith('MemAvailable:'))) * 1024
    disk = shutil.disk_usage(P).free
    assert ram >= 8 * 1024**3 and disk >= 25 * 1024**3
    out = dict(status='ROOT_APPROVED_UNCHANGED_ORIGINAL_PREOUTCOME_FROZEN_PARAMETER_JOB',
               approved_unix=time.time(), group=group, config=ref(config_path),
               case_sha256=CASE_SHA, seed=2026102754, config_pins_verified=pin_count,
               master=ref(MASTER), master_pins_verified=2042,
               all_previous_START_END_joined=len(starts), previous_supervisor_evidence=owner_evidence,
               all_previous_original_owner_PID_startticks_closed=True,
               no_source_model_recipe_threshold_or_checkpoint_reselection=True,
               original_three_valued_hard_stop_and_full_TASK_qualification_retained=True,
               own_past_trial_BO_fit_authorized_only_in_frozen_C4=group == 'V8CONVAL02',
               global_stop_unix=1793114740.0, physics_stop_unix=1793112940.0,
               last_child_start_unix=1793111740.0, job_wall_cap_s=config['job_wall_cap_s'],
               physical_timeout_s=600, free_ram_bytes=ram, free_disk_bytes=disk,
               preflight_source=ref(str(Path(__file__).relative_to(P))),
               new_model_scorer_map_fit_physics_calls=0)
    target = P / 'audit' / (group + '_MAIN_PHYSICS_APPROVAL_V1.json')
    with target.open('x') as stream:
        json.dump(out, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(group=group, status=out['status'], config_sha256=expected,
                          closed_prior_START_END=len(starts), pins=pin_count)))


if __name__ == '__main__':
    main()
