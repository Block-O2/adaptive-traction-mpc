#!/usr/bin/env python3
"""Prefix-free original-B TASK reproduction from the frozen m2 baseline source.

Fresh scratch only; no training/search. Uses original m2 source and original
seed 2026101303. Restores three missing support JSON objects only when their SHA
matches the original manifest. Literal path rebasing and all limits are recorded.
No historical raw byte identity is claimed without comparing historical raw.
"""
from __future__ import annotations
if not __debug__:
    raise SystemExit('Refusing optimized Python: original scientific assertion gates must remain enabled')
import argparse,hashlib,json,os,random,shutil,signal,sys,time,traceback
from pathlib import Path


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--prepare-only',action='store_true')
    ap.add_argument('--timeout-s',type=int,default=1800)
    a=ap.parse_args();repo=a.repo.resolve();dest=a.output.resolve()
    assert not dest.exists(),'Output must be a new directory'
    assert 600<=a.timeout_s<=3600
    src=repo/'research/side_studies/m2_18d_baseline_qualification_v1'
    support=repo/'research_archive/packages/deep_learning_method_exploration_v8/runtime'
    original_manifest=src/'EXECUTION_CODE_MANIFEST.json'
    original=json.loads(original_manifest.read_text())['files']
    plan0=json.loads((src/'RUN_PLAN.json').read_text())
    contract=json.loads((src/'BASELINE_CONTRACT.json').read_text())
    assert plan0['seed']==contract['development_seed']==2026101303
    assert contract['development_case']=='high_rom_nominal_sync_120_v1'
    assert contract['original_B_execution_required'] is True and contract['learning'] is False
    checked=[];missing=[]
    for rel,expected in original.items():
        f=src/rel
        if f.is_file():
            actual=sha(f)
            assert actual==expected,'ORIGINAL_SOURCE_IDENTITY_MISMATCH:'+rel
            checked.append(rel)
        else:missing.append(rel)
    dest.mkdir(parents=True)
    def ignore(directory,names):
        return [n for n in names if n in {'results','__pycache__','.git','.pytest_cache'} or n.endswith('.pyc')]
    for part in ['source','code','deps']:
        shutil.copytree(src/part,dest/part,ignore=ignore)
    for part in ['output','reports','motion_series','source/results','tmp/mpl','audit']:
        (dest/part).mkdir(parents=True,exist_ok=True)
    for name in ['FROZEN_18D.json','PARAMETER_MAP.json','MOTION_ACCEPTANCE_PROTOCOL.json','BASELINE_CONTRACT.json']:
        shutil.copy2(src/name,dest/name)
    action=src/'output/SHARED_COORDINATION_ACTION_CONTRACT.json'
    assert action.is_file();shutil.copy2(action,dest/'output'/action.name)
    restored=[]
    required=['source/stages/stage5_personalized_motion_learning/docs/high_rom_v1/PHASE_B_MATRIX.json',
              'deps/HISTORICAL_NATIVE_GRAPH_ACTIONS.json','deps/HISTORICAL_SPATIAL_GRAPH.json']
    for rel in required:
        f=dest/rel
        if f.is_file():assert sha(f)==original[rel],rel
        else:
            candidate=support/rel
            assert candidate.is_file() and sha(candidate)==original[rel],'MISSING_EXACT_SUPPORT:'+rel
            f.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(candidate,f)
            restored.append({'path':rel,'restored_from':str(candidate),'original_manifest_sha256':original[rel]})
    rebases=[];old='/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_baseline_qualification_v1'
    for f in sorted(dest.rglob('*.py')):
        before=f.read_text();after=before.replace(old,str(dest))
        if before!=after:
            row={'path':str(f.relative_to(dest)),'before_sha256':sha(f),'literal_path_replacements':before.count(old)}
            f.write_text(after);row['after_sha256']=sha(f);rebases.append(row)
    now=time.time()
    plan=dict(plan0)
    for key in ['hard_stop_unix','physics_hard_stop_unix','dispatch_cutoff_unix','validation_dispatch_cutoff_unix','no_new_physics_after_unix']:
        plan[key]=now+2*a.timeout_s+300
    plan.update(t0_unix=now,physical_timeout_s=a.timeout_s,purpose='One prefix-free original B archive reproduction; no search/training')
    dump(dest/'RUN_PLAN.json',plan)
    files={str(f.relative_to(dest)):sha(f) for f in sorted(dest.rglob('*')) if f.is_file()}
    m={'scope':'Original frozen m2 baseline source relocated; original task/parameters/seed',
       'historical_raw_exact_identity':'NOT_TESTED','source_package':str(src),
       'original_manifest_sha256':sha(original_manifest),'original_contract_sha256':sha(src/'BASELINE_CONTRACT.json'),
       'original_plan_sha256':sha(src/'RUN_PLAN.json'),'verified_existing_original_manifest_files':checked,
       'missing_original_manifest_objects':missing,'exact_hash_restored_support':restored,
       'literal_path_changes':rebases,'fresh_host_deadline_only':True,
       'scientific_parameter_changes':False,'prefix':{},'seed':2026101303,
       'missing_object_limit':'Original archival manifest is not complete: omitted historical support/metadata/weights and CPython3.10 native extensions are not claimed restored. This finite B route uses its archived Python source and records runtime native-prefix backend.',
       'files':files}
    dump(dest/'PREPARATION.json',m)
    if a.prepare_only:
        print(json.dumps({'status':'PREPARED_NOT_EXECUTED','package':str(dest),'original_source_files_verified':len(checked)}),flush=True);return
    assert shutil.disk_usage(dest).free>15*2**30,'DISK_FLOOR'
    mem=dict(x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines())
    assert int(mem['MemAvailable'].split()[0])>6*2**20,'RAM_FLOOR'
    os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
                      TMPDIR=str(dest/'tmp'),MPLCONFIGDIR=str(dest/'tmp/mpl'))
    sys.dont_write_bytecode=True;sys.path.insert(0,str(dest/'code'))
    import study_common as sc
    import matched_harness as mh
    import analyze_matched as am
    import numpy as np
    class OriginalB(mh.MatchedInterface):
        def decision_boundary(self,b):
            # Exact original Qualification.control behavior for arm B: no rich
            # planner and no prefix intervention, original zero residual table.
            return self.control(b)
    it=OriginalB({'name':'original_b','seed':2026101303,'prefix':{}})
    random.seed(2026101303);np.random.seed(2026101303)
    ident='original_b';start=time.monotonic()
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ARCHIVE_ORIGINAL_B_TIMEOUT')))
    signal.alarm(a.timeout_s)
    mh.event('START',ident,kind='PREFIX_FREE_ORIGINAL_B_ARCHIVE_REPRODUCTION',seed=2026101303,prefix={})
    try:
        metric=sc.run(ident,it,execution_mode='SCIENTIFIC_SIMULATION')
        measured=am.measure(ident);comparison=am.compare(measured,measured)
        with np.load(dest/'source/results'/ident/'trace.npz') as z:
            times=z['time_s'][z['stage']=='TASK'];task_duration=float(times[-1]-times[0])
        qualified=bool(metric['task_valid'] and metric['matched_eligible']
                       and measured['native_physical_audit']['pass_']
                       and measured['axes']['PHYSICAL_TASK_VALID']=='PASS'
                       and measured['axes']['SCIENTIFIC_EXECUTION_CAUSAL_VALID']=='PASS'
                       and measured['axes']['LEGACY_R2_MATCHED']=='PASS'
                       and comparison['acceptance_pass'] and abs(task_duration-19.03)<1e-8)
        summary=json.loads((dest/'source/results'/ident/'summary.json').read_text())
        backends=[]
        def collect_backends(value,path=''):
            if isinstance(value,dict):
                for key,item in value.items():
                    pointer=path+'/'+str(key)
                    if 'prefix_backend' in str(key):backends.append({'pointer':pointer,'value':item})
                    collect_backends(item,pointer)
            elif isinstance(value,list):
                for index,item in enumerate(value):collect_backends(item,path+'/'+str(index))
        collect_backends(summary)
        import importlib.metadata as metadata
        versions={name:metadata.version(name) for name in ['numpy','scipy','mujoco','gymnasium']}
        result={'status':'PASS' if qualified else 'FAIL_REPORTED_QUALIFICATIONS','task_duration_s':task_duration,
                'seed':2026101303,'prefix':{},'JF_N_s':measured['J_F_N_s'],'JM_Nm_s':measured['moment_integral_Nm_s'],
                'axes':measured['axes'],'original_motion_self_comparison':comparison,
                'source_scope':m['scope'],'historical_raw_exact_identity':'NOT_TESTED',
                'prefix_backend_records':backends,'runtime_versions':versions,
                'prefix_backend_default_in_original_source':'numpy',
                'wall_s':time.monotonic()-start,'training_steps':0,
                'host_qualification':'NOT_EVALUABLE','measured_path':'reports/original_b_MEASURED.json'}
        dump(dest/'RESULT.json',sc.clean(result))
        mh.event('END',ident,returncode=0 if qualified else 1,joined=True,task_valid=metric['task_valid'])
        print(json.dumps(sc.clean(result),ensure_ascii=False),flush=True)
        assert qualified,'PREFIX_FREE_B_ORIGINAL_QUALIFICATION_FAILURE'
    except BaseException as e:
        failure=json.loads((dest/'RESULT.json').read_text()) if (dest/'RESULT.json').exists() else {'status':'FAIL'}
        failure.update(error=str(e),traceback=traceback.format_exc(),wall_s=time.monotonic()-start)
        dump(dest/'RESULT.json',failure);raise
    finally:signal.alarm(0)


if __name__=='__main__':main()
