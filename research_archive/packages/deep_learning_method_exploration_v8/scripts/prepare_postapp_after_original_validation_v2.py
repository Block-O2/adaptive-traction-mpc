"""Root-reviewed metadata publication after all six original jobs close.
New fixed-development recipe identities only; no original models/labels changed.
"""
from pathlib import Path
import hashlib
import json
import os
import resource
import subprocess
import time

P=Path(__file__).resolve().parents[1]
H='families/critic_value/postvalidation_applicability_probe_v1/'
GROUPS=['V8VAL03','V8VAL04','V8FMEAN03','V8FMEAN04','V8CONVAL01','V8CONVAL02']
MASTER='freeze/COMPLETE_MODEL_PROCEDURE_PREVALIDATION_MASTER_V1.json'
DEST='source/v8_postapp_fixed_v2.py'
MANIFEST_SHA='e4cf864bde52de0c9bd401f451be37f6b7b006a5c69b889d63eedabf65038e88'
BUILDER_SHA='ddceb837584279b1078c43e5979de3c3b5c6b61a60e889742d4dc50a3d47791a'
WRAPPER_SHA='0ef9b7e34258860a581c06a564dee9e0092dcf2c4dac1d3d27c5832dcdf9ce0e'


def sha(relative):
    target=(P/relative).resolve();assert target.is_relative_to(P)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def read(relative):return json.loads((P/relative).read_text())


def ref(relative):return dict(path=relative,sha256=sha(relative))


def write(relative,value):
    with (P/relative).open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')


def identity(pid):
    try:ticks=int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:ticks=None
    return dict(pid=pid,start_ticks=ticks)


def main():
    assert time.time()<1793111740.0
    assert sha(MASTER)=='b7e41810af973c4af2fa9287c6801f37ae4ca0cee923e65e754c578ac83f728e'
    for rel,expected in read(MASTER)['frozen_artifacts'].items():assert sha(rel)==expected,rel
    assert sha(H+'SOURCE_MANIFEST_V2.json')==MANIFEST_SHA
    manifest=read(H+'SOURCE_MANIFEST_V2.json')
    for rel,expected in manifest['source_files_sha256'].items():assert sha(rel)==expected,rel
    assert sha(H+'prepare_metadata_candidate_v2.py')==BUILDER_SHA
    assert sha(H+'root_wrapper_candidate_v2.py')==WRAPPER_SHA
    assert not (P/DEST).exists()
    events=[json.loads(raw) for raw in (P/'runtime/ATTEMPTS.jsonl').read_bytes().splitlines()]
    starts={r['id']:r for r in events if r.get('event')=='START'};ends={r['id']:r for r in events if r.get('event')=='END'}
    assert starts.keys()==ends.keys() and all(r.get('joined') is True for r in ends.values())
    closed=[]
    for group in GROUPS:
        ids=[k for k,v in starts.items() if v['group']==group];assert ids
        ending='owned/'+group+'_SUPERVISOR_END.json';beginning='owned/'+group+'_SUPERVISOR.json'
        end,begin=read(ending),read(beginning);assert end['state']=='STOP' and not end['survivors']
        for owner in [begin['identity'],*end['known_owned'].values()]:assert identity(owner['pid'])['start_ticks']!=owner['start_ticks']
        closed.append(dict(group=group,START_END=len(ids),end=ref(ending),config=ref('experiments/'+group+'.json')))
    with (P/DEST).open('xb') as stream:stream.write((P/H/'root_wrapper_candidate_v2.py').read_bytes())
    assert sha(DEST)==WRAPPER_SHA
    runtime='freeze/POSTAPP_FIXED_DEVELOPMENT_MAIN_RUNTIME_APPROVAL_V2.json'
    write(runtime,dict(status='MAIN_APPROVED_EXPOSED_POSTVALIDATION_FIXED_APPLICABILITY_V2',
          approved_unix=time.time(),authorized_groups=['V8POSTAPP01','V8POSTAPP02'],
          source_manifest=ref(H+'SOURCE_MANIFEST_V2.json'),source_review=ref('audit/POSTAPP_MAIN_SOURCE_REVIEW_V2.json'),
          contract=ref(H+'PROBE_CONTRACT_V2.json'),original_all_six_jobs_closed=closed,
          global_stop_unix=1793114740.0,local_stop_unix=1793112940.0,
          new_model_fit_scorer_calls=0,original_raw_compare_per_case=1,
          separate_exact_physics_budget_required=True,child_wall_cap_s=600,job_wall_cap_s=1800,
          original_three_value_safety_and_full_qualification_contract_retained=True,
          additional_independent_condition_count=0,old_model_predictions_or_labels_transferred=False))
    output=P/H/'prepared/MAIN_V2_ONCE'
    now=time.time();approval='freeze/POSTAPP_METADATA_MAIN_APPROVAL_V2.json'
    write(approval,dict(status='MAIN_APPROVED_POSTAPP_METADATA_BUILD_ONLY_V2',builder_sha256=BUILDER_SHA,
          manifest_sha256=MANIFEST_SHA,issued_unix=now,expires_unix=now+60,
          output_absolute_path=str(output),model_map_fit_raw_scorer_physics_calls=0,
          runtime_approval=ref(runtime),main_publication_source=ref(str(Path(__file__).relative_to(P)))))
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1',
         'MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','VECLIB_MAXIMUM_THREADS':'1'}
    cmd=['/usr/bin/time','-v','-o',str(P/'audit/POSTAPP_METADATA_EXTERNAL_RESOURCE_V2.txt'),
         'timeout','-k','2','60','taskset','-c',str(min(os.sched_getaffinity(0))),
         'prlimit','--as=1073741824','--cpu=60','/home/hank/ihear-lab/rl_b_matched_recovery_stability_v1/offline-env/bin/python',
         '-B',str(P/H/'prepare_metadata_candidate_v2.py'),'--package',str(P),'--metadata-approval',str(P/approval),
         '--runtime-approval',str(P/runtime),'--output',str(output)]
    started=time.monotonic();before=resource.getrusage(resource.RUSAGE_CHILDREN)
    child=subprocess.Popen(cmd,env=env);owner=identity(child.pid);code=child.wait();after=resource.getrusage(resource.RUSAGE_CHILDREN)
    result=dict(status='CLOSED_METADATA_PREPARATION_ONLY',exit_code=code,launcher=identity(os.getpid()),child=owner,
          child_current=identity(child.pid),wall_s=time.monotonic()-started,
          inclusive_child_CPU_s=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
          approval=ref(approval),new_model_map_raw_scorer_fit_physics_calls=0,config_copies=[])
    if code==0:
        registration=read(str((output/'PREPARED_METADATA.json').relative_to(P)))
        for group in ['V8POSTAPP01','V8POSTAPP02']:
            src=str((output/(group+'.json')).relative_to(P));assert sha(src)==registration['config_sha256'][group]
            dest='experiments/'+group+'.json'
            with (P/dest).open('xb') as stream:stream.write((P/src).read_bytes())
            assert sha(dest)==sha(src);result['config_copies'].append(dict(prepared=ref(src),exact_root_copy=ref(dest)))
    write('audit/POSTAPP_METADATA_EXECUTION_V2.json',result);print(json.dumps(result))
    if code:raise SystemExit(code)


if __name__=='__main__':main()
