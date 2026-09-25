"""Campaign fresh48: frozen original distribution, durable all-proposal ledger."""
from copy import deepcopy
from datetime import datetime,timezone
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
from traction_mpc_stage5.fresh_qualification_v1.domain import TASK_FAMILIES,RANGE_CELLS,draw_proposal,mechanical_screen,canonical_json_hash
from traction_mpc_stage5.rigid_table_assembly_v1 import repaired_counterpart,assess_assembly,MIN_PROXIMAL_GAP_M
from run_autonomous_recovery_v1 import DOC,OUT,ROOT,ASSEMBLY,source_manifest
CONTRACT='autonomous_closed_loop_recovery_v1_fresh48_v1'

def require(ok,message):
    if not ok:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def atomic(path,value):
    path=Path(path);temp=path.with_name(path.name+'.pending')
    with temp.open('w') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def exclusive(path,value):
    path=Path(path)
    with path.open('x') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)

def bind_seed_series(seed_path,seeds,batch):
    path=DOC/'QUALIFICATION_SERIES.json'
    identity={'contract':CONTRACT,'seed_manifest_sha256':sha(seed_path),'root_seeds':seeds['root_seeds']}
    if path.exists():require(json.loads(path.read_text())==identity,'Qualification seed series changed')
    else:
        require(batch==1 and not list(OUT.glob('fresh_batch_*/ATTEMPT_CONSUMED.json')),'Missing original seed series')
        exclusive(path,identity)
    return sha(path)

def reserve_execution(bundle_path,directory,manifest,*,resume=False):
    import fcntl
    bundle_path=Path(bundle_path);directory=Path(directory)
    lock=(bundle_path/'EXECUTION.lock').open('a')
    try:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        identity={'contract':CONTRACT,'output_directory':str(directory.resolve()),
                  'bundle_sha256':sha(bundle_path/'manifest.json'),'candidate_seal_sha256':manifest['candidate_seal_sha256'],
                  'case_keys':[r['case_key'] for r in manifest['rows']]}
        path=bundle_path/'EXECUTION_RESERVATION.json'
        if path.exists():
            require(resume,'Bundle already reserved; only explicit same-directory continuation is allowed')
            require(json.loads(path.read_text())==identity,'Cannot redirect or repeat consumed qualification bundle')
        else:
            require(not resume,'Cannot resume an unreserved execution')
            exclusive(path,identity)
        # Caller retains the lock for its entire serial batch. Existing STARTED rows
        # are reconciled as interrupted, never rerun or replaced by a later success.
    except BaseException:
        lock.close()
        raise
    return lock

def journal(path,value):
    with Path(path).open('a') as f:
        f.write(json.dumps(value,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def slots(batch):
    return [{'case_key':f'b{batch:02d}_{f}_{name}_r{r:02d}','family':f,'range':name,'range_index':ri,'replicate':r,'status':'NOT_EXPOSED','valid':False}
            for r in range(1,5) for f in TASK_FAMILIES for ri,name in enumerate(RANGE_CELLS)]

def slot_seed(batch,root,family,range_index,replicate):
    payload=f'autonomous_closed_loop_recovery_v1:fresh48:v1:{batch}:{root}:{family}:{range_index}:{replicate}'
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8],'big')

def validate_roots(seeds):
    require(seeds['contract']==CONTRACT,'Seed contract mismatch')
    roots=seeds['root_seeds'];require(len(roots)==3 and len(set(roots))==3,'Three unique presealed roots required')
    require(all(type(x) is int and 0<=x<2**64 for x in roots),'uint64 roots required')
    forbidden=seeds['forbidden_roots'];require({18386242844751736710,4711001}.issubset(forbidden),'Missing exposed roots')
    require(not any(x in forbidden for x in roots),'Root previously exposed')

def verify_artifacts(files):
    require(bool(files),'Evidence hashes missing')
    for name,digest in files.items():require(sha(ROOT/name)==digest,'Modified sealed artifact: '+name)

def validate_candidate(seal):
    require(seal['contract']==CONTRACT,'Candidate contract mismatch')
    require(seal['source_sha256']==source_manifest(persist=False),'Candidate source changed')
    verify_artifacts(seal['qualification_artifacts_sha256'])
    gate_path=ROOT/seal['development_gate_path'];require(sha(gate_path)==seal['development_gate_sha256'],'Gate changed')
    gate=json.loads(gate_path.read_text());verify_artifacts(gate['evidence_sha256'])
    require(gate['source_sha256']==seal['source_sha256'],'Development source differs from candidate')
    require(gate['controller_options']==seal['controller_options'],'Development options differ from candidate')
    require(gate['schema']=='independent_autonomous_recovery_development_gate_v1','Independent gate schema')
    require(gate['executable_denominator']==23 and len(gate['case_results'])==23,'Development denominator')
    require(len({x['case_key'] for x in gate['case_results']})==23,'Duplicate development cases')
    original=json.loads((ASSEMBLY/'OLD_TO_NEW_CASE_MAPPING.json').read_text())
    expected={x['case_key'] for x in original if x['v2_validity']['valid']}
    require(len(expected)==23 and {x['case_key'] for x in gate['case_results']}==expected,'Development case substitution')
    for item in gate['case_results']:
        require(all(item[x] is True for x in ('native_safety','true_task','wall_evidence','reference_20ms','timing','truth_firewall')),'Development case gate failed')
    require(all(gate[x] is True for x in ('dual_quality_gate','source_audit_passed','relevant_tests_passed')),'Development cohort/source gate failed')

def extend_v2(case,v1):
    case=deepcopy(case);extension={'rule':'unchanged_from_v1','added_upward_shift_m':0.0}
    if not v1['valid'] and v1['category']=='INVALID_FIXED_GEOMETRY' and v1['reason']=='MuJoCo reset overlap: sleeve':
        gap=float(v1['initial']['distances']['sleeve']['minimum_signed_distance_m']);needed=MIN_PROXIMAL_GAP_M-gap
        proposed=float(case['physical']['hip_translation_xz_m'][1])+needed
        extension={'rule':'minimum_positive_sleeve_table_installation_clearance','v1_initial_sleeve_gap_m':gap,
                   'required_added_upward_shift_m':needed,'proposed_hidden_hip_shift_z_m':proposed,
                   'maximum_legal_hidden_hip_shift_z_m':.006,'added_upward_shift_m':0.,
                   'within_registered_installation_range':proposed<=.006+1e-9}
        if extension['within_registered_installation_range']:
            case['physical']['hip_translation_xz_m'][1]=proposed;extension['added_upward_shift_m']=needed
    return case,extension

def check_budget():
    state=json.loads((DOC/'STATE.json').read_text())
    require(state['status']=='CONTINUE' and not (DOC/'STOP').exists(),'Campaign not active')
    elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(state['started_at_utc'])).total_seconds()
    require(elapsed<state['budget']['maximum_active_seconds'],'Campaign time exhausted')
    require(state['budget']['new_rollouts']<state['budget']['maximum_new_rollouts'],'Rollout budget exhausted')
    return state

def verify_bundle(path):
    path=Path(path);manifest=json.loads((path/'manifest.json').read_text())
    require(sha(path/'manifest.json')==(path/'MANIFEST.sha256').read_text().strip(),'Bundle hash mismatch')
    require(manifest['status']=='SEALED' and manifest['contract']==CONTRACT,'Bundle not released')
    require(type(manifest['batch']) is int and 1<=manifest['batch']<=3,'Invalid batch')
    require(manifest['registered_slots']==48 and type(manifest['root_seed']) is int,'Invalid denominator/root type')
    expected=slots(manifest['batch']);require([x['case_key'] for x in manifest['rows']]==[x['case_key'] for x in expected],'48-slot order mismatch')
    for actual,exp in zip(manifest['rows'],expected):
        require(all(actual[k]==exp[k] for k in ('family','range','range_index','replicate')),'Cell mismatch')
        require('case_path' in actual,'Sealed slot is missing its retained case')
        if 'case_path' in actual:
            require(sha(actual['case_path'])==actual['case_sha256'],'Case file changed')
            require(canonical_json_hash(json.loads(Path(actual['case_path']).read_text()))==actual['final_case_canonical_sha256'],'Case content changed')
            require(actual['valid'] is actual['v2_validity']['valid'],'Case validity mismatch')
            require(actual['status']==('READY' if actual['valid'] else 'PRECHECK_REJECTED'),'Case status mismatch')
        require(actual['slot_seed']==slot_seed(manifest['batch'],manifest['root_seed'],actual['family'],actual['range_index'],actual['replicate']),'Slot seed mismatch')
    seal=json.loads(Path(manifest['candidate_seal_path']).read_text());require(sha(manifest['candidate_seal_path'])==manifest['candidate_seal_sha256'],'Seal changed');validate_candidate(seal)
    require(manifest['source_sha256']==seal['source_sha256'] and manifest['controller_options']==seal['controller_options'],'Bundle candidate mismatch')
    require(sha(manifest['seed_manifest_path'])==manifest['seed_manifest_sha256'],'Seeds changed')
    seeds=json.loads(Path(manifest['seed_manifest_path']).read_text());validate_roots(seeds)
    require(manifest['root_seed']==seeds['root_seeds'][manifest['batch']-1],'Wrong root for batch')
    series=DOC/'QUALIFICATION_SERIES.json'
    require(sha(series)==manifest['series_sha256'],'Original seed series changed')
    require(json.loads(series.read_text())=={'contract':CONTRACT,'seed_manifest_sha256':manifest['seed_manifest_sha256'],'root_seeds':seeds['root_seeds']},'Seed series mismatch')
    require(sha(path/'ATTEMPT_CONSUMED.json')==manifest['consumption_sha256'],'Consumption changed')
    consumed=json.loads((path/'ATTEMPT_CONSUMED.json').read_text())
    require(all(consumed[k]==manifest[k] for k in ('contract','batch','root_seed','candidate_seal_sha256','seed_manifest_sha256')),'Attempt identity mismatch')
    require(consumed['case_keys']==[r['case_key'] for r in manifest['rows']],'Attempt denominator mismatch')
    return manifest,seal

def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--batch',type=int,choices=(1,2,3),required=True)
    p.add_argument('--seed-manifest',type=Path,required=True);p.add_argument('--candidate-seal',type=Path,required=True)
    a=p.parse_args();seeds=json.loads(a.seed_manifest.read_text());seal=json.loads(a.candidate_seal.read_text())
    validate_roots(seeds);validate_candidate(seal);state=check_budget()
    require(state['budget']['qualification_batches_used']==a.batch-1,'Attempt accounting mismatch')
    series_hash=bind_seed_series(a.seed_manifest,seeds,a.batch)
    output=OUT/f'fresh_batch_{a.batch:02d}';output.mkdir(exist_ok=False);(output/'cases').mkdir()
    root=seeds['root_seeds'][a.batch-1]
    manifest={'contract':CONTRACT,'batch':a.batch,'registered_slots':48,'status':'RESERVED',
              'seed_manifest_path':str(a.seed_manifest.resolve()),'seed_manifest_sha256':sha(a.seed_manifest),
              'candidate_seal_path':str(a.candidate_seal.resolve()),'candidate_seal_sha256':sha(a.candidate_seal),
              'source_sha256':seal['source_sha256'],'controller_options':seal['controller_options'],
              'root_seed':root,'rows':slots(a.batch),'proposals':0,'series_sha256':series_hash}
    atomic(output/'manifest.json',manifest)
    # Directory creation plus immutable durable marker prevents duplicate exposure.
    # On interruption this marker is authoritative even if STATE reconciliation lagged.
    atomic(output/'ATTEMPT_CONSUMED.json',{'contract':CONTRACT,'batch':a.batch,'root_seed':root,
        'case_keys':[x['case_key'] for x in manifest['rows']], 'candidate_seal_sha256':sha(a.candidate_seal),
        'seed_manifest_sha256':sha(a.seed_manifest),'started_at_utc':datetime.now(timezone.utc).isoformat()})
    state['budget']['qualification_batches_used']=a.batch;atomic(DOC/'STATE.json',state)
    manifest['consumption_sha256']=sha(output/'ATTEMPT_CONSUMED.json');manifest['status']='GENERATING';atomic(output/'manifest.json',manifest)
    try:
      for row in manifest['rows']:
        check_budget();key=row['case_key'];seed=slot_seed(a.batch,root,row['family'],row['range_index'],row['replicate'])
        row['slot_seed']=seed;rng=np.random.Generator(np.random.PCG64(seed));accepted=None
        for pi in range(1,31):
            check_budget();case=draw_proposal(rng,family=row['family'],range_index=row['range_index'],replicate=row['replicate'],proposal_index=pi);case['case_key']=key
            journal(output/'proposals.jsonl',{'event':'PROPOSAL_DRAWN','case':case,'canonical_sha256':canonical_json_hash(case),'slot_seed':seed})
            manifest['proposals']+=1;row['status']='SCREENING';atomic(output/'manifest.json',manifest)
            try:screen=mechanical_screen(case)
            except BaseException as error:
                journal(output/'proposals.jsonl',{'event':'SCREEN_EXCEPTION','case_key':key,'proposal_index':pi,'error':repr(error)});raise
            journal(output/'proposals.jsonl',{'event':'SCREEN_RESULT','case_key':key,'proposal_index':pi,'screen':screen})
            if screen['accepted']:accepted=case;break
        if accepted is None:row.update(status='GENERATION_EXHAUSTED',valid=False)
        else:
            v1,mapping=repaired_counterpart(accepted);v1check=assess_assembly(v1);final,extension=extend_v2(v1,v1check);v2check=assess_assembly(final)
            row.update(raw_case=accepted,raw_canonical_sha256=canonical_json_hash(accepted),v1_case=v1,v1_canonical_sha256=canonical_json_hash(v1),
                       v1_mapping=mapping,v1_validity=v1check,envelope_extension=extension,v2_validity=v2check,valid=v2check['valid'],
                       status='READY' if v2check['valid'] else 'PRECHECK_REJECTED',final_case_canonical_sha256=canonical_json_hash(final),
                       changed_fields_from_v1=[] if canonical_json_hash(v1)==canonical_json_hash(final) else ['physical.hip_translation_xz_m[1]'])
            casepath=output/'cases'/f'{key}.json';atomic(casepath,final);row.update(case_path=str(casepath.resolve()),case_sha256=sha(casepath))
        atomic(output/'manifest.json',manifest);print(json.dumps({'case_key':key,'status':row['status'],'proposals':manifest['proposals']}),flush=True)
      manifest['status']='GENERATION_INCOMPLETE' if any(r['status']=='GENERATION_EXHAUSTED' for r in manifest['rows']) else 'SEALED'
    except BaseException as error:
      manifest.update(status='INTERRUPTED_OR_FAILED',error=repr(error));raise
    finally:
      atomic(output/'manifest.json',manifest)
      with (output/'MANIFEST.sha256').open('x') as f:f.write(sha(output/'manifest.json')+'\n');f.flush();os.fsync(f.fileno())
if __name__=='__main__':main()
