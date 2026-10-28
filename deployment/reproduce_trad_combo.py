#!/usr/bin/env python3
"""Reproduce frozen v7 DEVPC02 B / V6PHASE / TRAD_COMBO with original worker.

No search, model fitting or training. Linux os.fork is required. Mechanical path
rebasing and fresh host execution deadlines are recorded in PREPARATION.json.
"""
from __future__ import annotations
if not __debug__:
    raise SystemExit("Refusing optimized Python: original scientific assertion gates must remain enabled")
import argparse, hashlib, json, os, shutil, sys, time
from pathlib import Path


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--prepare-only',action='store_true')
    ap.add_argument('--timeout-s',type=int,default=1800,
                    help='Per branch host timeout; original simulated task duration is unchanged')
    a=ap.parse_args();repo=a.repo.resolve();dest=a.output.resolve()
    assert not dest.exists(),'Output must be a new directory'
    assert 600 <= a.timeout_s <= 3600
    src=repo/'research_archive/packages/autonomous_learning_smoothness_v7'
    original=src/'experiments/DEVPC02.json'
    assert original.is_file(),f'Missing frozen config: {original}'
    cfg=json.loads(original.read_text())
    assert cfg['worker']=='v7_worker_v5.py' and cfg['group']=='DEVPC02'
    assert cfg['condition']['seed']==2026102690
    assert cfg['condition']['prefix']=={'OUTBOUND':[[.068,.042,.024]],'RETURN':[[.047,.026,.019]]}
    cfg['actions']=[x for x in cfg['actions'] if x['tag'] in ['B','V6PHASE','TRAD_COMBO']]
    assert [x['tag'] for x in cfg['actions']]==['B','V6PHASE','TRAD_COMBO']
    combo=cfg['actions'][-1]['action']
    assert combo['x']==[-.18310670132483464,0.,0.,-.9571745795248379,.5,1.,-1.,-.95]
    assert combo['legacy']==[.8245887463260377,-.9835625245511301]
    # Original optional cross-package repeated-history audit only; original
    # physical/task/motion/scorer and parent-state gates remain active.
    omitted_history=cfg['historical_repeats'];cfg['historical_repeats']={}
    dest.mkdir(parents=True)
    def ignore(directory,names):
        return [n for n in names if n in {'results','__pycache__','.git','.pytest_cache'} or n.endswith('.pyc')]
    shutil.copytree(src/'source',dest/'source',ignore=ignore)
    for part in ['source','code','control','deps']:
        shutil.copytree(src/'runtime'/part,dest/'runtime'/part,ignore=ignore)
    for f in (src/'runtime').glob('*.json'):shutil.copy2(f,dest/'runtime'/f.name)
    for part in ['runtime/output','runtime/reports','runtime/motion_series','runtime/source/results',
                 'runtime/tmp/mpl','audit','attempts','history','jobs/DEVPC02','owned','experiments',
                 'predictions','freeze']:(dest/part).mkdir(parents=True,exist_ok=True)
    for rel in ['runtime/output/SHARED_COORDINATION_ACTION_CONTRACT.json',
                'freeze/VARIED_HUMAN_SPLIT_V1.json','freeze/DEVPC02.json','audit/CLOSURE_RELOCATION.json']:
        assert (src/rel).is_file(),f'Missing required original closure object: {src/rel}'
        shutil.copy2(src/rel,dest/rel)
    old='/home/hank/ihear-lab/autonomous_learning_smoothness_v7'
    replacements=[]
    for f in sorted(dest.rglob('*.py')):
        before=f.read_text();after=before.replace(old,str(dest))
        if before!=after:
            row={'path':str(f.relative_to(dest)),'before_sha256':sha(f),'literal_path_replacements':before.count(old)}
            f.write_text(after);row['after_sha256']=sha(f);replacements.append(row)
    dump(dest/'experiments/DEVPC02.json',cfg)
    dump(dest/'runtime/DEVPC02_TEST_PLAN.json',cfg)
    now=time.time();end=now+6*a.timeout_s+1200
    plan={'t0_unix':now,'hard_stop_unix':end,'physics_hard_stop_unix':end-300,
          'dispatch_cutoff_unix':end-300,'validation_dispatch_cutoff_unix':end-300,
          'no_new_physics_after_unix':end-300,'physical_timeout_s':a.timeout_s,
          'all_physics_serial':True,'physics_budget':4,'development_cap':4,
          'min_ram_gib':6,'min_disk_gib':20,'fixed_global_attempt_cap':None,
          'fixed_global_native_step_cap':None,'purpose':'Finite archive reproduction, no search/training'}
    dump(dest/'runtime/RUN_PLAN.json',plan)
    dump(dest/'ACTIVATION.json',{'activation_id':'archive_reproduction_DEVPC02','t0_unix':now,
         'hard_stop_unix':end,'deadline_unix':end,'state':'ARCHIVE_REPRODUCTION',
         'authorization':'2026-10-28 user requested reproducible archive verification',
         'historical_campaign_resumed':False})
    files={str(f.relative_to(dest)):sha(f) for f in sorted(dest.rglob('*'))
           if f.is_file() and f.suffix in {'.py','.json','.xml','.obj','.stl'}}
    m={'scope':'Fresh finite v7 traditional reproduction','source_package':str(src),
       'original_config_sha256':sha(original),'literal_path_changes':replacements,
       'controller_parameters_changed':False,'plant_task_scorer_safety_changed':False,
       'fresh_host_deadlines':True,'filtered_actions':['B','V6PHASE','TRAD_COMBO'],
       'omitted_optional_cross_package_history_audit':omitted_history,
       'historical_identity_not_claimed_by_this_launcher':True,'files':files}
    dump(dest/'PREPARATION.json',m)
    # Import-time legacy modules need these real, newly computed manifests.
    manifest={'files':{str(f.relative_to(dest/'runtime')):sha(f) for f in sorted((dest/'runtime').rglob('*'))
                       if f.is_file() and f.suffix in {'.py','.json','.xml','.obj','.stl'}
                       and f.name not in {'EXECUTION_CODE_MANIFEST.json','EXECUTION_CODE_MANIFEST_v6.json'}},
              'scope':'Fresh runtime hashes; see PREPARATION.json'}
    dump(dest/'runtime/EXECUTION_CODE_MANIFEST.json',manifest)
    dump(dest/'runtime/EXECUTION_CODE_MANIFEST_v6.json',manifest)
    if a.prepare_only:
        print(json.dumps({'status':'PREPARED_NOT_EXECUTED','package':str(dest)}),flush=True);return
    os.environ.update(ACL2_PACKAGE=str(dest),STUDY_GROUP='DEVPC02',STUDY_MODE='development',
                      OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                      TMPDIR=str(dest/'runtime/tmp'),MPLCONFIGDIR=str(dest/'runtime/tmp/mpl'))
    sys.dont_write_bytecode=True
    sys.path[:0]=[str(dest/'source'),str(dest/'runtime/control'),str(dest/'runtime/code')]
    sys.argv=[str(Path(__file__).resolve()),'experiments/DEVPC02.json']
    import v7_worker_v5 as w
    start=time.monotonic()
    try:
        w.main()
        rows=[json.loads((dest/'attempts'/('DEVPC02_'+tag+'_RESULT.json')).read_text())
              for tag in ['B','V6PHASE','TRAD_COMBO']]
        import v7_metrics_v3 as native_metrics
        for row in rows:
            native_metrics.evaluate(row['id'])
        paired = native_metrics.compare('DEVPC02')
        combo_quality = next(x for x in paired if x['id']=='DEVPC02_TRAD_COMBO')
        original_pass = all(r.get('complete') and r.get('qualified') for r in rows)
        extra_pass = combo_quality['both_cost_improvement_and_quality'] is True
        final_status = 'PASS' if original_pass and extra_pass else ('FAIL_REPORTED_QUALIFICATIONS' if not original_pass else 'FAIL_FROZEN_EXTRA_QUALITY')
        out={'status':final_status,
             'frozen_quality_contract':json.loads((dest/'freeze/DEVPC02.json').read_text())['quality_contract'],
             'original_native_quality_comparison':paired,
             'native_metrics_paths':['analysis/native_metrics/'+x['id']+'.json' for x in rows],
             'wall_s':time.monotonic()-start,'rows':rows,'training_steps':0,
             'clock':'SCIENTIFIC_SIMULATION','host_qualification':'NOT_EVALUABLE'}
        dump(dest/'RESULT.json',out);print(json.dumps(out,ensure_ascii=False),flush=True)
        assert out['status']=='PASS','ARCHIVE_QUALIFICATION_FAILURE'
    except BaseException as e:
        if not (dest/'RESULT.json').exists():dump(dest/'RESULT.json',{'status':'FAIL','error':str(e),'wall_s':time.monotonic()-start})
        raise


if __name__=='__main__':main()
