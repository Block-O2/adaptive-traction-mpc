"""Read-only final byte checks of original master and every executed job pin."""
from pathlib import Path
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]


def main():
    started = time.time()
    cache, failures, checks, references = {}, [], [], {}

    def sha(rel):
        path = (P / rel).resolve()
        assert path.is_relative_to(P)
        if rel not in cache:
            cache[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        return cache[rel]

    def read(rel):
        references[rel] = sha(rel)
        return json.loads((P / rel).read_text())

    master_rel = 'freeze/COMPLETE_MODEL_PROCEDURE_PREVALIDATION_MASTER_V1.json'
    assert sha(master_rel) == 'b7e41810af973c4af2fa9287c6801f37ae4ca0cee923e65e754c578ac83f728e'
    master = read(master_rel)
    assert len(master['frozen_artifacts']) == 2042
    sources = [(master_rel, master['frozen_artifacts'])]
    snap_rel = 'audit/PHYSICAL_ACCOUNTING_FINAL_EXACT_V1.json'
    snap = read(snap_rel)
    assert snap['status'] == 'CLOSED_EXACT'
    for group in sorted(snap['groups']):
        end = read('owned/' + group + '_SUPERVISOR_END.json')
        assert end['state'] == 'STOP' and not end['survivors']
        config_rel = 'experiments/' + group + '.json'
        config = read(config_rel)
        job_rel = 'jobs/' + group + '/SOURCE_MANIFEST.json'
        job = read(job_rel)
        assert job['config_sha256'] == sha(config_rel)
        sources.append((config_rel, config['frozen_artifacts']))
        sources.append((job_rel, job['files']))
    for container, pins in sources:
        matched = 0
        for rel, expected in pins.items():
            assert time.time() < 1793114740.0
            try:
                actual = sha(rel)
                if actual != expected:
                    failures.append(dict(container=container, path=rel, expected=expected, actual=actual))
                else:
                    matched += 1
            except OSError as error:
                failures.append(dict(container=container, path=rel, expected=expected, error=str(error)))
        checks.append(dict(container=container, pins=len(pins), matched=matched))
    result = dict(schema='v8.final_all_executed_source_model_pin_verification.v1',
                  status='PASS' if not failures else 'FAIL_PRESERVED', created_unix=time.time(),
                  original_master_sha256=sha(master_rel), original_master_pins=2042,
                  model_containers=7, model_artifact_references=49, procedure_artifact_references=91,
                  reference_counts_are_not_independent_trained_models_or_trials=True,
                  executed_physical_groups=len(snap['groups']), containers=checks,
                  unique_rehashed_files=len(cache), actual_SHA256=cache, references=references,
                  failures=failures, wall_s=time.time()-started,
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  model_scorer_fit_physics_calls=0)
    with (P / 'audit/FINAL_PINNED_SOURCE_MODEL_VERIFICATION_V1.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k:result[k] for k in ['status','executed_physical_groups','unique_rehashed_files','failures']}))
    if failures:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
