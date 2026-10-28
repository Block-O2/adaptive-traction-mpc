#!/usr/bin/env python3
"""Fresh, serial D01R B/H150 reproduction; no training or parameter search.

Copies the sealed runtime into a new output directory, rebases literal source
paths, and creates a fresh wall-clock execution allowance. The original runtime,
plant, task, scorer, admission, and all controller parameters remain unchanged.
Linux os.fork is required. Never run this script inside an existing result dir.
"""
from __future__ import annotations
if not __debug__:
    raise SystemExit("Refusing optimized Python: original scientific assertion gates must remain enabled")
import argparse, hashlib, json, os, shutil, signal, sys, time, traceback
from pathlib import Path


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--prepare-only', action='store_true')
    p.add_argument('--timeout-s', type=int, default=1800,
                   help='Per physical branch host timeout; does not alter simulated task duration')
    args = p.parse_args()
    repo, target = args.repo.resolve(), args.output.resolve()
    assert not target.exists(), 'Output directory must be new'
    assert 600 <= args.timeout_s <= 3600
    src = repo / 'research_archive/packages/deep_learning_method_exploration_v8/runtime'
    cfgpath = repo / 'research/side_studies/ihear_overnight_control_learning_transition_v1/D01R_PLAN.json'
    assert src.is_dir(), f'Missing archived runtime: {src}'
    assert cfgpath.is_file(), f'Missing exact D01R configuration: {cfgpath}'
    target.mkdir(parents=True)
    runtime = target / 'runtime'
    runtime.mkdir()
    def ignore(directory, names):
        return [n for n in names if n in {'__pycache__', '.git', 'results', '.pytest_cache'} or n.endswith('.pyc')]
    for part in ['source', 'code', 'control', 'deps']:
        shutil.copytree(src / part, runtime / part, ignore=ignore)
    for f in src.glob('*.json'):
        shutil.copy2(f, runtime / f.name)
    # This new reproduction never inherits campaign outcomes, STOP markers or attempts.
    for part in ['output', 'reports', 'motion_series', 'tmp/mpl', 'audit']:
        (runtime / part).mkdir(parents=True, exist_ok=True)
    (runtime / 'source/results').mkdir(parents=True)
    # This frozen scientific contract is historically stored beside outputs.
    contract = src / 'output/SHARED_COORDINATION_ACTION_CONTRACT.json'
    assert contract.is_file(), f'Missing frozen action contract: {contract}'
    shutil.copy2(contract, runtime / 'output' / contract.name)
    changes = []
    old = '/home/hank/ihear-lab/deep_learning_method_exploration_v8/runtime'
    # Replacement is confined to literal path text. Record exact before/after hashes.
    for f in sorted(runtime.rglob('*.py')):
        before = f.read_text()
        after = before.replace(old, str(runtime))
        if after != before:
            changes.append({'path':str(f.relative_to(runtime)), 'before_sha256':sha(f),
                            'path_replacements':before.count(old)})
            f.write_text(after)
            changes[-1]['after_sha256'] = sha(f)
    cfg = json.loads(cfgpath.read_text())
    cfg['arms'] = [arm for arm in cfg['arms'] if arm['id'] in ['B', 'H150']]
    assert [arm['id'] for arm in cfg['arms']] == ['B', 'H150']
    assert cfg['condition']['seed'] == 2026102001 and cfg['fork_after_prefix'] == 1
    # These are frozen original scientific identities, not values inferred from results.
    assert cfg['condition']['prefix'] == {'OUTBOUND':[[.08,.04,.03]], 'RETURN':[[.04,.02,.03]]}
    assert cfg['arms'][1]['candidate_hash'] == '255b40496f100c5d78956da64102276993c9995965fbfa610bd00a3967102931'
    cfg['reproduce_W1'] = False  # Original D01R value; no external historical raw needed.
    dump(runtime / 'D01R_TEST_PLAN.json', cfg)
    now = time.time()
    plan = {'t0_unix':now, 'hard_stop_unix':now+args.timeout_s*5+1200,
            'physics_hard_stop_unix':now+args.timeout_s*5+600,
            'dispatch_cutoff_unix':now+args.timeout_s*4+600,
            'validation_dispatch_cutoff_unix':now+args.timeout_s*4+600,
            'no_new_physics_after_unix':now+args.timeout_s*5+600,
            'physical_timeout_s':args.timeout_s, 'physics_budget':3, 'development_cap':3,
            'all_physics_serial':True, 'purpose':'Archive reproduction only, no search/training'}
    dump(runtime / 'RUN_PLAN.json', plan)
    files = {str(f.relative_to(runtime)):sha(f) for f in sorted(runtime.rglob('*'))
             if f.is_file() and f.suffix in {'.py','.json','.xml','.stl','.obj'}
             and f.name not in {'EXECUTION_CODE_MANIFEST.json','EXECUTION_CODE_MANIFEST_v6.json'}}
    manifest = {'files':files, 'scope':'Fresh reproduction copy; literal path rebasing only',
                'original_runtime':str(src), 'original_D01R_config_sha256':sha(cfgpath),
                'path_changes':changes, 'scientific_parameter_changes':False,
                'original_deadline_replaced_by_fresh_execution_allowance':True,
                'arms_filtered_to_frozen_B_and_H150':True}
    # Existing import-time dependencies expect these manifest names. Both contain
    # actual hashes; no historical PREPHYSICAL_CHECKS or PASS result is fabricated.
    dump(runtime / 'EXECUTION_CODE_MANIFEST.json', manifest)
    dump(runtime / 'EXECUTION_CODE_MANIFEST_v6.json', manifest)
    dump(target / 'PREPARATION.json', manifest)
    if args.prepare_only:
        print(json.dumps({'status':'PREPARED_NOT_EXECUTED','runtime':str(runtime)}), flush=True)
        return
    os.environ.update(STUDY_GROUP='D01R', STUDY_MODE='development',
                      OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                      TMPDIR=str(runtime/'tmp'), MPLCONFIGDIR=str(runtime/'tmp/mpl'))
    sys.dont_write_bytecode=True
    sys.path[:0]=[str(runtime/'control'), str(runtime/'code')]
    # Original interface_base reads sys.argv at import; give it its historical group.
    sys.argv=[str(Path(__file__).resolve()), 'D01R']
    import campaign_v6 as c
    import numpy as np
    import random
    it=c.Campaign(cfg['condition'])
    ident='D01R_parent'
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('ARCHIVE_OWNED_TIMEOUT')))
    signal.alarm(args.timeout_s*5+600)
    c.dispatch(ident, kind='ARCHIVE_LEGAL_COLD_PARENT', condition=cfg['condition'])
    random.seed(cfg['condition']['seed']); np.random.seed(cfg['condition']['seed'])
    start=time.monotonic()
    try:
        result=c.sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
        if it.child is not None:
            os._exit(0)
        c.mh.event('END',ident,returncode=0,joined=True,task_valid=result['task_valid'])
        assert result['task_valid'], 'PARENT_TASK_INVALID'
        parent=c.am.measure(ident)
        gate=c.bc.compare_raw(runtime/'source/results'/ident,runtime/'source/results/D01R_B')
        dump(target/'PARENT_B_GATE.json',gate)
        assert gate['status']=='PASS','PARENT_B_RAW_DIFFERENCE'
        expected_ids={'D01R_B','D01R_H150'}
        qualified=(len(it.results)==2 and {row.get('id') for row in it.results}==expected_ids
                   and all(row.get('complete_task') is True
                           and row.get('all_original_qualifications') is True for row in it.results))
        out={'status':'PASS' if qualified else 'FAIL_REPORTED_QUALIFICATIONS', 'wall_s':time.monotonic()-start,
             'clock':'SCIENTIFIC_SIMULATION','host_qualification':'NOT_EVALUABLE',
             'rows':it.results, 'parent_task_duration_s':result.get('task_duration'),
             'parent_JF_N_s':parent['J_F_N_s'], 'parent_B_raw_gate':gate,
             'training_steps':0, 'hardware_actuation':False}
        dump(target/'RESULT.json',c.sc.clean(out))
        print(json.dumps(c.sc.clean(out),ensure_ascii=False),flush=True)
        assert qualified, 'ARCHIVE_ORIGINAL_QUALIFICATION_FAILURE'
    except BaseException as exc:
        if it.child is not None:
            dump(runtime/'reports'/('D01R_'+it.child['kind']+'_ARCHIVE_ERROR.json'),
                 {'error':str(exc),'traceback':traceback.format_exc()})
            os._exit(1)
        failure=json.loads((target/'RESULT.json').read_text()) if (target/'RESULT.json').exists() else {'status':'FAIL'}
        failure.update(error=str(exc),traceback=traceback.format_exc(),wall_s=time.monotonic()-start)
        dump(target/'RESULT.json',failure)
        raise
    finally:
        signal.alarm(0)


if __name__=='__main__':
    main()
