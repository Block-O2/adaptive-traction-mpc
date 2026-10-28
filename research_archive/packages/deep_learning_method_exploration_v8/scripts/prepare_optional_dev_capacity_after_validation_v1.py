"""Root-reviewed publication gate, run only after all six original jobs close.
Installs only the new exact wrapper, creates explicit runtime/metadata authority,
and invokes the reviewed metadata-only builder. No maps/models/physics here.
"""
from pathlib import Path
import hashlib
import json
import os
import resource
import subprocess
import time

P = Path(__file__).resolve().parents[1]
HERE = 'families/ppo_reward/continuous_scale_v1/development_axis_capacity_v1/'
GROUPS = ['V8VAL03', 'V8FMEAN03', 'V8CONVAL01', 'V8VAL04', 'V8FMEAN04', 'V8CONVAL02']
DEST = 'source/v8_fixed_development_axis_capacity_v1.py'
MASTER = 'freeze/COMPLETE_MODEL_PROCEDURE_PREVALIDATION_MASTER_V1.json'
MASTER_SHA = 'b7e41810af973c4af2fa9287c6801f37ae4ca0cee923e65e754c578ac83f728e'
EXPECTED = {
    'SOURCE_MANIFEST_V1.json': '4c25d6659f8f67791b7190786d71e5a7079f8b9b2a668060040e8669ca74ca80',
    'RUNTIME_SOURCE_REQUIREMENTS_V1.json': '937dab679e848acc38ddf2ec3e1010ef4615ecef3ca12e4ea2533c79906e8d75',
    'prepare_metadata_candidate_v1.py': 'ed92d3023f423d188af2e7fd2e7c94b08d950cda797f8615e60136987ae0ab35',
    'root_wrapper_candidate_v1.py': '45f6e1ab94d3bc7c5d11603a789df1d44a986678db341eb4738afead4b39a2cf',
}


def sha(relative):
    target = (P / relative).resolve()
    assert target.is_relative_to(P)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def read(relative):
    return json.loads((P / relative).read_text())


def ref(relative):
    return dict(path=relative, sha256=sha(relative))


def write(relative, value):
    with (P / relative).open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False); stream.write('\n')


def identity(pid):
    try:
        ticks = int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    except FileNotFoundError:
        ticks = None
    return dict(pid=pid, start_ticks=ticks)


def main():
    assert time.time() < 1793111740.0
    assert sha(MASTER) == MASTER_SHA
    for rel, expected in read(MASTER)['frozen_artifacts'].items():
        assert sha(rel) == expected, rel
    for suffix, expected in EXPECTED.items():
        assert sha(HERE + suffix) == expected, suffix
    manifest = read(HERE + 'SOURCE_MANIFEST_V1.json')
    for rel, expected in manifest['files_sha256'].items():
        assert sha(rel) == expected, rel
    requirements = read(HERE + 'RUNTIME_SOURCE_REQUIREMENTS_V1.json')
    sources = requirements['runtime_sources_sha256']
    assert len(sources) == 1396
    assert sources[DEST] == EXPECTED['root_wrapper_candidate_v1.py']
    assert not (P / DEST).exists()
    for rel, expected in sources.items():
        if rel != DEST:
            assert sha(rel) == expected, rel
    events = [json.loads(raw) for raw in (P / 'runtime/ATTEMPTS.jsonl').read_bytes().splitlines()]
    starts = {row['id']: row for row in events if row.get('event') == 'START'}
    ends = {row['id']: row for row in events if row.get('event') == 'END'}
    assert starts.keys() == ends.keys() and all(row.get('joined') is True for row in ends.values())
    reviews = []
    for group in GROUPS:
        ids = [key for key, value in starts.items() if value['group'] == group]
        assert ids
        end_path = 'owned/' + group + '_SUPERVISOR_END.json'
        begin_path = 'owned/' + group + '_SUPERVISOR.json'
        end, begin = read(end_path), read(begin_path)
        assert end['state'] == 'STOP' and not end['survivors']
        for owner in [begin['identity'], *end['known_owned'].values()]:
            assert identity(owner['pid'])['start_ticks'] != owner['start_ticks']
        reviews.append(dict(group=group, starts=len(ids), ends=len(ids), config=ref('experiments/'+group+'.json'),
                            supervisor_end=ref(end_path), worker_exit_code=end['worker_exit_code']))
    assert all((P/'owned'/ (group+'_SUPERVISOR_END.json')).exists() for group in {r['group'] for r in starts.values()})
    closed_path = 'audit/ALL_SIX_ORIGINAL_PARAMETER_JOBS_CLOSED_BEFORE_DEV_CAPACITY_V1.json'
    write(closed_path, dict(status='ROOT_ALL_SIX_ORIGINAL_FROZEN_JOBS_CLOSED', checked_unix=time.time(),
                           reviews=reviews, all_START_END_closed=len(starts), no_outcome_retraining_or_recipe_replacement=True,
                           global_stop_unix=1793114740.0, new_model_map_scorer_physics_calls=0))
    with (P/DEST).open('xb') as target:
        target.write((P/HERE/'root_wrapper_candidate_v1.py').read_bytes())
    assert sha(DEST) == sources[DEST]
    runtime_path = 'freeze/DEV_CAPACITY_FIXED_PROTOCOL_MAIN_RUNTIME_APPROVAL_V1.json'
    write(runtime_path, dict(schema='v8.dev_axis_capacity_runtime_main_approval.v1',
          status='MAIN_APPROVED_FIXED_EXPOSED_DEV_CAPACITY_ONLY', approved_unix=time.time(),
          authorized_groups=['V8DEVCAP01H','V8DEVCAP01L'], required_new_parameter_jobs_closed=True,
          required_new_parameter_jobs_closed_review=ref(closed_path), source_files_sha256=sources,
          pure_map_calls_per_case=5, model_calls=0, global_stop_unix=1793114740.0,
          local_stop_unix_by_group={'V8DEVCAP01H':1793112940.0,'V8DEVCAP01L':1793112940.0},
          job_wall_cap_s=1800, child_wall_cap_s=600, serial_dispatch_after_separate_actual_config_review_only=True,
          not_new_independent_validation_or_policy_training=True))
    now = time.time()
    approval_path = 'freeze/DEV_CAPACITY_METADATA_MAIN_APPROVAL_V1.json'
    write(approval_path, dict(schema='v8.dev_axis_capacity_metadata_main_approval.v1',
          status='MAIN_APPROVED_METADATA_PREPARATION_ONLY', builder_sha256=EXPECTED['prepare_metadata_candidate_v1.py'],
          source_manifest=ref(HERE+'SOURCE_MANIFEST_V1.json'), source_files_sha256=sources,
          runtime_approval=ref(runtime_path), local_start_unix=now, local_stop_unix=now+60,
          global_stop_unix=1793114740.0, model_map_fit_RNG_physics_calls=0,
          main_source_review=ref('audit/DEVELOPMENT_AXIS_CAPACITY_MAIN_SOURCE_REVIEW_V1.json')))
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'OPENBLAS_NUM_THREADS':'1',
           'OMP_NUM_THREADS':'1','MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1'}
    command = ['/usr/bin/time','-v','-o', str(P/'audit/DEV_CAPACITY_METADATA_EXTERNAL_RESOURCE_V1.txt'),
               'timeout','-k','2','60','/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python','-B',
               str(P/HERE/'prepare_metadata_candidate_v1.py'),'--package',str(P),'--approval',str(P/approval_path),
               '--approval-sha256',ref(approval_path)['sha256']]
    start=time.monotonic(); before=resource.getrusage(resource.RUSAGE_CHILDREN)
    child=subprocess.Popen(command,env=env); owner=identity(child.pid); code=child.wait()
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    result=dict(status='CLOSED_METADATA_PREPARATION_ONLY',exit_code=code,launcher=identity(os.getpid()),
                child=owner,child_current=identity(child.pid),wall_s=time.monotonic()-start,
                inclusive_child_CPU_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                approval=ref(approval_path),source=ref(str(Path(__file__).relative_to(P))),
                new_model_map_scorer_fit_physics_calls=0)
    write('audit/DEV_CAPACITY_METADATA_EXECUTION_V1.json',result)
    print(json.dumps(result))
    if code:
        raise SystemExit(code)


if __name__ == '__main__':
    main()
