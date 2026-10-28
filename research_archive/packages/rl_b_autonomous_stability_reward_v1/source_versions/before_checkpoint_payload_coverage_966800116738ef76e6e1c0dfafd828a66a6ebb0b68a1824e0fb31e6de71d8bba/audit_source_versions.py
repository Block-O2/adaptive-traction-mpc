"""Recheck every used source bundle and saved training checkpoint provenance."""
from pathlib import Path
import hashlib
import json
import shutil
import re
from research_common import ROOT, atomic, read, sha, now


def audit():
    previous = ROOT/'audit/USED_SOURCE_BUNDLE_VERIFICATION.json'
    if previous.exists():
        archive = ROOT/'audit/source_verification_snapshots'/f'{sha(previous)}.json'
        archive.parent.mkdir(exist_ok=True)
        if not archive.exists():
            shutil.copyfile(previous, archive)
    ledger = read(ROOT/'LEDGER.json')
    physical_jobs = {a['job'] for a in ledger['attempts']}
    source_index = {}
    for p in (ROOT/'source_versions').glob('*/*.py'):
        source_index.setdefault((p.name, sha(p)), []).append(str(p))
    bundles = []
    checkpoints = []
    missing = []
    historical_recovery = []
    zero_physics = []
    for start in sorted((ROOT/'jobs').glob('*/START.json')):
        job = start.parent.name
        s = read(start)
        identity = read(start.parent/'SOURCE_IDENTITY.json')
        checks = {}
        if identity:
            checks = {name: (Path(identity['path'])/name).exists() and
                      sha(Path(identity['path'])/name) == expected
                      for name, expected in identity['files'].items()}
            calculated = hashlib.sha256(json.dumps(identity['files'], sort_keys=True).encode()).hexdigest()
            checks['bundle_hash'] = calculated == identity['bundle_sha256']
            checks['directory_identity'] = Path(identity['path']).name == identity['bundle_sha256']
            checks['config_file_sha'] = sha(s['config']) == s['config_sha256']
            bundles.append(dict(job=job, bundle_sha256=identity['bundle_sha256'],
                                checks=checks, pass_=all(checks.values())))
        elif job not in physical_jobs:
            zero_physics.append(job)
        elif job != 'control_seed1495656323_first5__repair1':
            missing.append(dict(job=job, reason='PHYSICAL_JOB_WITHOUT_SOURCE_BUNDLE_IDENTITY'))
        for p in sorted((ROOT/'runtime/jobs'/job/'checkpoints').glob('episode_*.json')):
            if not re.fullmatch(r'episode_\d+\.json',p.name):
                continue
            meta = read(p)
            expected = {'worker.py': meta['research_source_sha256'],
                        'rewards.py': meta['reward_source_sha256']}
            if identity:
                cc = {name: identity['files'].get(name) == value for name, value in expected.items()}
            else:
                cc = {name: bool(source_index.get((name, value))) for name, value in expected.items()}
                historical_recovery.append(dict(checkpoint=str(p),
                    recorded_sources=expected,
                    preserved_sources={name:source_index.get((name, value), []) for name, value in expected.items()},
                    pass_=all(cc.values())))
            cc['raw_config_file_sha'] = meta['research_config_sha256'] == sha(s['config'])
            if meta.get('effective_config_path'):
                cc['effective_config_sha'] = sha(meta['effective_config_path']) == meta['effective_config_sha256']
            if meta.get('pending_complete_transitions'):
                cc['pending_data_sha'] = sha(meta['pending_complete_rollout_path']) == meta['pending_complete_rollout_sha256']
                pending=read(meta['pending_complete_rollout_path'])
                cc['pending_policy_identity']=meta['pending_generated_under_policy_sha256']==meta['policy_sha256']
                cc['pending_sample_count']=len(pending)==meta['pending_complete_transitions']
                cc['pending_episode_count']=sum(bool(x['episode_start']) for x in pending)==meta['pending_complete_episodes']
                cc['pending_complete_boundaries']=bool(pending and pending[0]['episode_start'] and pending[-1]['terminal'])
                cc['pending_each_reset_boundary']=all(bool(b['episode_start'])==bool(a['terminal']) for a,b in zip(pending,pending[1:]))
            checkpoints.append(dict(checkpoint=str(p), job=job, checks=cc, pass_=all(cc.values())))
    bad = [x for x in bundles+checkpoints if not x['pass_']]
    result = dict(time_utc=now(), pass_=not bad and not missing,
        source_sha256=sha(Path(__file__)), jobs_with_content_addressed_bundles=len(bundles),
        physical_jobs=len(physical_jobs), bundles=bundles, checkpoints=checkpoints,
        initial_control_worker_source_recovery=historical_recovery,
        initial_control_import_provenance_evidence='audit/EARLY_CONTROL_REWARD_SOURCE_RECOVERY.json',
        initial_control_import_provenance_note='Early Control001 original reward source was exactly recovered. Later002-005 on-disk file SHA metadata do not prove reloading an already imported module. Both preserved reward implementations return the identical unmodified R0 baseline, and strict full Control reproduction passed. Frozen later bundles are distinct from this early metadata limitation.',
        zero_physics_program_attempts=zero_physics, mismatches=bad+missing,
        scope='Actual used outer job identities, byte-checked content-addressed worker/reward/common bundles, saved training checkpoint code/config/pending provenance. Frozen runtime identity is audited separately; zero new physics or Adam.')
    atomic(previous, result)
    return result


if __name__ == '__main__':
    result = audit()
    print(json.dumps(dict(pass_=result['pass_'], bundles=len(result['bundles']),
                         checkpoints=len(result['checkpoints']), mismatches=len(result['mismatches']))))
    raise SystemExit(0 if result['pass_'] else 1)
