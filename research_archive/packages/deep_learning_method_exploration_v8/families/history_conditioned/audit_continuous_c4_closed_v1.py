"""SOURCE_ONLY bounded, separately approved CLOSED C4 original audit.

The complete-task audit function is reused unchanged from its frozen original
source. This entry adds C4 metadata authority, explicit missing/alias roles,
partial original-scorer checks, and generic stored BO accounting. Never run on
an active job. No source, checkpoint, worker, model or root artifact is changed.
"""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
import resource
import signal
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REL = 'families/history_conditioned/'
COMMON = REL + 'audit_continuous_closed_v1.py'
COMMON_SHA = '6d20e0ec481ff755c4e7e95bd968082d7a04460b8fdde0e7dee4f1dcd5035bfa'
MANIFEST = REL + 'C4_CLOSED_AUDIT_SOURCE_MANIFEST_V1.json'
CONTRACT = REL + 'C4_CLOSED_AUDIT_CONTRACT_V1.json'
STOP = 1793114740.0
GROUPS = {
    'V8CONVAL01': ('cb5e746e608b60c11154b0607a27620b2a86e6f95d3370799b70861792d9e28c', 2026102753, '8a0fccf993531c07cd9ca646c541b75e7b0799c756b0e297f8a176c19f5011a4'),
    'V8CONVAL02': ('224e40773dfc6c1ce44c643db99ffcc0c921c120a3ab203ae849e355409a8b87', 2026102754, 'af16c44145d4ba204730b7b9e88b91620689ee2c6caff40ffd9f06185b9091a0'),
}
TASK_SUFFIXES = ['T1_B', 'T2_parent', 'T2_B', 'T2_ZERO_MODAL', 'T2_H150',
    'T2_H150_T3_parent', 'T2_H150_T3_B', 'T2_H150_T3_H150',
    'T2_H150_T3_ZERO_MODAL', 'T2_H150_T3_ILC_ENABLED_G025',
    'T2_H150_T3_ILC_ENABLED_G010', 'T2_H150_T3_FIXED_X3_MINUS025',
    'T2_H150_T3_FIXED_X3_PLUS025', 'T2_H150_T3_ILC_HISTORY_DISABLED']
BOUNDARY_SUFFIXES = ['BOUNDARY_1_2', 'T2_H150_BOUNDARY_2_3']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def need(test, reason):
    if not test:
        raise ValueError(reason)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def metadata_gate(root, group):
    """No raw access: original actual C4 config/protocol/master only."""
    config_path = root / 'experiments' / (group + '.json')
    config = load(config_path)
    case_sha, seed, config_sha = GROUPS[group]
    need(sha(config_path) == config_sha, 'EXACT_ACTUAL_PREOUTCOME_C4_CONFIG')
    need(config['mode'] == 'validation' and config['case_sha256'] == case_sha and
         config['condition']['seed'] == seed and config['worker'] == 'v8_continuous_ilc_worker_v4.py',
         'ORIGINAL_C4_GROUP_CASE_SEED_WORKER')
    protocol_path = root / config['continuous_validation_protocol']
    need(sha(protocol_path) == config['continuous_validation_protocol_sha256'], 'ACTUAL_FROZEN_C4_PROTOCOL')
    protocol = load(protocol_path)
    need(sha(protocol_path) == '27e5d06f6879f6470d1d737175b087b6ac4e6401421f808ecc22c95bd630a4f1', 'EXACT_ACTUAL_C4_PROTOCOL')
    need(protocol['status'] == 'APPROVED_FROZEN_PROCEDURE_NEW_PARAMETER_VALIDATION_V1' and
         protocol['original_global_stop_unix'] == STOP and
         protocol['registered_base_tasks'] == 14 and protocol['registered_inter_rep_boundaries'] == 2 and
         protocol['optional_legal_BO_child_max'] == 1, 'ORIGINAL_C4_REGISTERED_PROCEDURE')
    master_path = root / protocol['root_full_inventory_path']
    need(sha(master_path) == protocol['root_full_inventory_sha256'], 'ACTUAL_PREOPEN_MASTER')
    master = load(master_path)
    need(sha(master_path) == 'b7e41810af973c4af2fa9287c6801f37ae4ca0cee923e65e754c578ac83f728e', 'EXACT_ACTUAL_COMPLETE_MASTER')
    need(protocol['original_inventory_sections'] == {key: master[key] for key in
         ('frozen_artifacts', 'model_inventory', 'strong_control_inventory', 'procedure_inventory')},
         'ALL_ORIGINAL_MODEL_AND_PROCEDURE_SECTIONS')
    manifest_path = root / 'jobs' / group / 'SOURCE_MANIFEST.json'
    manifest = load(manifest_path)
    need(manifest['config_sha256'] == sha(config_path) and
         manifest.get('continuous_validation_protocol_sha256') == sha(protocol_path), 'ACTUAL_JOB_CONFIG_PROTOCOL_BINDING')
    for relative in (REL + 'continuous_ilc_worker_v4.py', 'source/v8_continuous_ilc_worker_v4.py',
                     'source/v8_case_adapter_v2.py'):
        expected = config['frozen_artifacts'].get(relative)
        need(expected and sha(root / relative) == expected and manifest['files'].get(relative) == expected,
             'ACTUAL_C4_ADAPTER2_SOURCE_CLOSURE:' + relative)
    return dict(config_sha256=sha(config_path), protocol_sha256=sha(protocol_path),
        master_sha256=sha(master_path), case_sha256=case_sha, seed=seed,
        job_source_manifest_sha256=sha(manifest_path), original14tasks2boundaries_optionalBO1=True)


def partial_original_scoring(root, result, common, counts):
    """Exactly one original evaluate per actual incomplete TASK if readable.

    A missing original summary/trace/archive is an explicit evidence gap. It is
    never replaced with full motion arrays, a force rank or a safe hard status.
    """
    partials = [row for row in result['trials'] if row.get('complete_original') is not True]
    if not partials:
        return []
    helper, _ = common.original_helpers()
    mode, _, _ = helper.original_functions(root)
    config = load(root / 'experiments' / (counts['group'] + '.json'))
    case_path = root / config['case_path']; case = load(case_path)
    descriptor = dict(case_key=case['case_key'], physical_variant=case['cell']['family'],
        candidate=case['coordination_candidate'], path=str(case_path.relative_to(root / 'runtime/source')), sha256=sha(case_path))
    scoring = load(root / 'runtime/source/stages/stage5_personalized_motion_learning/docs/high_rom_v1/PHASE_B_MATRIX.json')['scoring']
    records = []
    for row in partials:
        ident = row['id']; path = root / 'runtime/source/results' / ident
        evidence = dict(id=ident, complete=False, full_motion_arrays=None,
            full_force_or_moment_rank_allowed=False, full_qualification_imputed=False)
        if not all((path / name).is_file() for name in ('summary.json', 'trace.npz', 'runtime_artifacts.json.gz', 'HIGH_ROM_CASE_RESULT.json')):
            evidence.update(status='ORIGINAL_PARTIAL_SCORER_INPUTS_MISSING_NOT_IMPUTED', hard11_status='UNKNOWN')
            result['errors'].append(ident + ':PARTIAL_ORIGINAL_SCORER_UNAVAILABLE')
        else:
            counts['partial_original_evaluator_entered'] += 1
            fresh = common.clean(mode.evaluate(helper.ArchivePath(path), descriptor, scoring,
                goal_deg=case['task']['goal_deg'], start_deg=case['task']['start_deg']))
            counts['partial_original_evaluator_returned'] += 1
            hard = {key: fresh['physical_task_result']['scorer_v2_common_conditions'].get(key) for key in common.HARD}
            evidence.update(status='ORIGINAL_PARTIAL_REPLAY_NOT_RANKED', original_evaluator=fresh,
                hard11=hard, hard11_status='TRUE_HARD' if any(v is False for v in hard.values()) else
                'ALL_TRUE' if all(v is True for v in hard.values()) else 'UNKNOWN')
            data_path = root / 'runtime/output' / (ident + '_DATA.json')
            if data_path.is_file():
                cached = load(data_path).get('metric', {}).get('physical_audit', {}).get('unchanged_evaluator')
                if cached is not None:
                    for key in ('physical_task_result', 'scientific_validity', 'overall_result_for_mode', 'raw_scorer_v2'):
                        if fresh[key] != cached[key]:result['errors'].append(ident + ':PARTIAL_CACHE_BYPASS_MISMATCH:' + key)
            if any(v is not True for v in hard.values()):result['errors'].append(ident + ':PARTIAL_HARD_FALSE_OR_UNKNOWN')
        row['C4_partial_original_replay'] = evidence
        records.append(evidence)
    return records


def role_coverage(group, closed, result):
    started = set(closed['ids']); aliases = {Path(x['path']).name.removesuffix('_ALIAS.json'): x for x in result['aliases']}
    by_id = {row['id']: row for row in result['trials']}
    by_id.update({row['id']: row for row in result['boundaries']})
    roles = []
    for suffix in TASK_SUFFIXES + BOUNDARY_SUFFIXES + ['T2_H150_T3_BO_V2_NEW']:
        ident = group + '_' + suffix
        if ident in started:
            state = 'ACTUAL_STARTED_CLOSED_BOUNDARY' if suffix in BOUNDARY_SUFFIXES else 'ACTUAL_STARTED_CLOSED_TASK'
            need(ident in by_id, 'ACTUAL_START_MISSING_AUDIT:' + ident)
        elif ident in aliases:
            state = 'EXPLICIT_ZERO_NEW_STEPS_ALIAS_NOT_ANOTHER_TASK'
        else:
            state = 'NOT_RUN_GATED_OR_STOPPED_NO_OUTCOME_IMPUTED'
        roles.append(dict(id=ident, status=state, optional=suffix.endswith('BO_V2_NEW'),
            boundary_no_TASK_scorer=suffix in BOUNDARY_SUFFIXES,
            alias=aliases.get(ident)))
    return roles


def actual_modal_reference_review(root, group, result):
    """Audit actual selected target/positive receipt and raw reference effect.

    Uses the original completed component-audit expressions, generalized only
    to actual C4 group IDs. No controller or model is called.
    """
    import numpy as np
    by_id={row['id']:row for row in result['trials']}
    alias={Path(row['path']).name.removesuffix('_ALIAS.json'):row['record']['alias_of'] for row in result['aliases']}
    reviews=[]
    for ident,trial in by_id.items():
        action=trial.get('worker_result',{}).get('action',{})
        if trial.get('complete_original') is not True or action.get('family')!='modal8_retimed' or not any(action.get('x',[])):
            continue
        zero=group+('_T2_H150_T3_ZERO_MODAL' if '_T3_' in ident else '_T2_ZERO_MODAL')
        zero=alias.get(zero,zero);bad=[]
        if zero not in by_id or by_id[zero].get('complete_original') is not True:
            reviews.append(dict(id=ident,status='NO_COMPLETE_SAME_STAGE_ZERO_REFERENCE',errors=['MISSING_ZERO_REFERENCE']));continue
        with np.load(root/'runtime/source/results'/zero/'trace.npz',allow_pickle=False) as z:
            zt=z['time_s'];zref=z['reference_q_rad']
        with np.load(root/'runtime/source/results'/ident/'trace.npz',allow_pickle=False) as f:
            t=f['time_s'];ref=f['reference_q_rad'];indices=np.clip(np.searchsorted(zt,t),0,len(zt)-1);left=np.maximum(indices-1,0)
            indices=np.where(abs(zt[left]-t)<abs(zt[indices]-t),left,indices);common=abs(zt[indices]-t)<1e-8
            difference=float(np.max(abs(ref[common]-zref[indices[common]]),initial=0.))
        summary=load(root/'runtime/source/results'/ident/'summary.json')
        lineage=load(root/'runtime/reports'/(ident+'_EXECUTED_RESIDUAL_RECEIPTS.json'));owners={row['decision_index']:row for row in lineage['rows']};windows=[]
        for row in summary['learning_records']:
            meta=row.get('selected_plan',{}).get('execution_screen',{}).get('coordination_modal_v2')
            if meta is None:continue
            changed=np.max(abs(np.asarray(meta['proposed_target_rad'])-np.asarray(meta['original_target_rad'])))>1e-12
            if not changed:continue
            own=owners[row['decision_index']]
            good=meta['status']=='ACCEPTED' and row.get('selected_plan_activated') is True and own['actual_native_steps']>0 and np.allclose(row['selected_plan']['target_q_rad'],meta['proposed_target_rad'],atol=1e-12,rtol=0)
            windows.append(dict(decision_index=row['decision_index'],accepted_activated_selected_target_and_positive_native=bool(good),actual_native_steps=own['actual_native_steps']))
        if not windows or not all(row['accepted_activated_selected_target_and_positive_native'] for row in windows) or difference<=1e-12:bad.append('ACTUAL_REFERENCE_NOT_JUST_PROPOSAL')
        reviews.append(dict(id=ident,zero_reference=zero,status='PASS_ACTUAL_NONZERO_REFERENCE' if not bad else 'REVIEW_REQUIRED',reference_maxdiff_rad=difference,windows=windows,errors=bad))
    return reviews


def stored_bo_review(root, group, result):
    """Stored observation/receipt/selection review: never fit or predict."""
    documents = {Path(x['path']).name: x for x in result['BO_original_artifacts_only']}
    output = dict(status='NOT_RUN_NO_STORED_BO_DECISION', new_model_fit_predict=0, errors=[])
    for item in documents.values():need(sha(root / item['path']) == item['sha256'], 'BO_STORED_ARTIFACT_CHANGED')
    bundles = [v for k, v in documents.items() if k.endswith('_OBSERVATION_BUNDLE.json')]
    decisions = [v for k, v in documents.items() if k.endswith('_DECISION.json')]
    abstentions = [v for k, v in documents.items() if k.endswith('_ABSTAIN.json')]
    receipts = [v['record'] for k, v in documents.items() if '_FIT_RECEIPT_' in k]
    output['actual_original_fit_receipts'] = receipts
    if abstentions and not decisions:
        output.update(status='GATED_OR_BUDGET_ABSTAIN_ORIGINAL_PAID_PREFIX_RETAINED', original=abstentions,
            actual_original_fit_receipt_count=len(receipts))
        return output
    if not decisions:return output
    need(len(decisions) == len(bundles) == 1, 'ONE_CURRENT_T3_BO_DECISION_ONLY')
    bundle = bundles[0]['record']; decision = decisions[0]['record']; bad = output['errors']
    if digest(bundle) != decision['input_sha256']:bad.append('BO_EXACT_INPUT_DIGEST')
    if decision['owner_before_hash'] != decision['owner_after_hash'] or decision['owner_before_hash'] != bundle['parent_snapshot_sha256']:
        bad.append('BO_PARENT_STATE_MUTATED')
    rows = {row['id']: row for row in result['trials']}; strong = rows.get(group + '_T2_H150_T3_H150')
    observations = []
    for row in bundle['observations']:
        trial = rows.get(row['id']); errors = []
        if trial is None or strong is None or trial.get('independent_qualified') is not True:errors.append('MISSING_OWN_COMPLETED_QUALIFIED_OBSERVATION')
        else:
            if abs(row['delta_JF_N_s'] - (trial['JF_N_s'] - strong['JF_N_s'])) > 1e-10:errors.append('JF_COMPONENT_LABEL')
            if abs(row['delta_JM_Nm_s'] - (trial['JM_Nm_s'] - strong['JM_Nm_s'])) > 1e-10:errors.append('JM_COMPONENT_LABEL')
        observations.append(dict(id=row['id'], x3=row['x3'], errors=errors));bad.extend(errors)
    names = decision['head_names']; grid = []
    for index, stored in enumerate(decision['grid_audit']):
        x = stored['x3']; reasons = []
        if any(abs(x - q) <= 1e-12 for q in bundle['attempted_x3']):reasons.append('ALREADY_ATTEMPTED_SEMANTIC_X3')
        upperF=[]; upperM=[]; lower=[]
        for predictions in decision['predictions'].values():
            pred=predictions[index];need(pred['x3']==x,'BO_QUERY_IDENTITY')
            upperF.append(pred['mean'][names[0]] + 2*pred['spread'][names[0]])
            upperM.append(pred['mean'][names[1]] + 2*pred['spread'][names[1]])
            lower.extend(pred['mean'][name] - 2*pred['spread'][name] for name in names[2:])
        if max(upperF)>decision['best_observed_qualified']['delta_JF_N_s']-.01:reasons.append('NO_ALL_MODEL_CONSERVATIVE_FORCE_INCREMENT')
        if max(upperM)>0:reasons.append('JM_COMPONENT_RISK')
        if min(lower)<0:reasons.append('ORIGINAL_MOTION_COMPONENT_RISK')
        if reasons!=stored['reasons'] or (not reasons)!=stored['eligible']:bad.append('BO_STORED_GRID_RULE')
        grid.append(dict(x3=x,eligible=not reasons,reasons=reasons))
    eligible=[x for x in decision['grid_audit'] if x['eligible']]
    selected=min(eligible,key=lambda x:(x['worst_model_JF_upper_N_s'],-x['minimum_model_component_lower_margin'],abs(x['x3']),x['x3'])) if eligible else None
    if decision['status'] != ('PROPOSE_ONE_FROZEN_GRID_ACTION' if selected else 'ABSTAIN') or decision['selected_x3'] != (selected['x3'] if selected else None):bad.append('BO_EXACT_SELECTED_OR_ABSTAIN')
    if sorted(x['index'] for x in receipts)!=list(range(1,decision['fit_matrix_solves']+1)):bad.append('BO_ACTUAL_RECEIPT_INDEX_COVERAGE')
    output.update(status='PASS_STORED_BO_ONLY' if not bad else 'REVIEW_REQUIRED', observations=observations, stored_grid=grid,
        original_decision_status=decision['status'], actual_original_fit_matrix_solves=decision['fit_matrix_solves'],
        output_heads_per_solve=decision['scalar_heads'], no_fixed_old42_or_ABSTAIN_assumption=True,
        actual_original_fit_CPU_s=decision.get('cpu_s'), actual_original_extraction_plus_fit_CPU_s=decision.get('extraction_plus_fit_cpu_s'))
    new_id = group + '_T2_H150_T3_BO_V2_NEW'
    candidate = rows.get(new_id)
    if decision['status'] == 'ABSTAIN' and candidate is not None:bad.append('BO_CHILD_AFTER_ABSTAIN')
    if candidate is not None:
        if candidate['worker_result'].get('action') != decision['selected_action']:bad.append('BO_NEW_CHILD_FROZEN_ACTION')
        events=[json.loads(line) for line in (root/'runtime/ATTEMPTS.jsonl').read_text().splitlines() if line]
        first=next(event for event in events if event.get('id')==new_id and event.get('event')=='START')
        if (root/decisions[0]['path']).stat().st_mtime >= first['unix'] or decision.get('freeze_before_any_new_candidate_START') is not True:
            bad.append('BO_CHOICE_NOT_FROZEN_BEFORE_NEW_CHILD')
        output['new_candidate_scope']='ACTUAL_ORIGINAL_TASK_AUDITED_SEPARATELY_NOT_A_PREDICTED_QUALIFICATION'
    else:output['new_candidate_scope']='NOT_RUN_NO_TASK_IMPUTED'
    output['status']='PASS_STORED_BO_ONLY' if not bad else 'REVIEW_REQUIRED'
    return output


def main():
    start=time.monotonic();cpu=time.process_time()
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--group',choices=GROUPS,required=True)
    ap.add_argument('--closed-job-approved',action='store_true');ap.add_argument('--approval',required=True);ap.add_argument('--approval-sha256',required=True)
    args=ap.parse_args();root=Path(args.root).resolve();approval_path=Path(args.approval).resolve()
    need(root==ROOT and args.closed_job_approved and approval_path.is_relative_to(root),'EXACT_ROOT_GROUP_SEPARATE_CLOSED_APPROVAL')
    need(sha(approval_path)==args.approval_sha256,'EXACT_CLOSED_AUDIT_APPROVAL')
    authority=load(approval_path);contract=load(root/CONTRACT);manifest=load(root/MANIFEST)
    need(authority.get('schema')=='v8.C4.closed_original_audit_approval.v1' and authority.get('status')=='ROOT_APPROVED_ONE_CLOSED_C4_AUDIT_V1' and
         authority.get('group')==args.group and authority.get('source_manifest_sha256')==sha(root/MANIFEST) and authority.get('contract_sha256')==sha(root/CONTRACT) and
         authority.get('budget')==contract['budget'] and authority.get('new_model_fit_predict_physics')==0,'SEPARATE_EXACT_CLOSED_READONLY_AUTHORITY')
    need(sys.dont_write_bytecode and Path(sys.executable).resolve()==Path('/home/hank/ihear-lab/rl_b_cloud_v1/.venv/bin/python').resolve() and
         all(os.environ.get(k)=='1' for k in ['PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']),'MAIN_VENV_MINUS_B_THREADS1')
    deadline=min(start+240.,start+STOP-time.time());need(time.monotonic()<deadline,'ORIGINAL_CLOCK_NO_RESET')
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(2147483648,2147483648));resource.setrlimit(resource.RLIMIT_CPU,(240,240))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('C4_CLOSED_AUDIT_ORIGINAL_DEADLINE')))
    signal.setitimer(signal.ITIMER_REAL,deadline-time.monotonic())
    for relative,expected in manifest['files_sha256'].items():need(sha(root/relative)==expected,'AUDIT_DEPENDENCY_CHANGED:'+relative)
    need(sha(root/COMMON)==COMMON_SHA,'ORIGINAL_GENERIC_AUDIT_CHANGED')
    common=module(root/COMMON,'_readonly_C4_original_generic_audit')
    # Mandatory whole-tree metadata closure precedes the first raw/evaluator read.
    closed=common.closure(root,args.group);need(closed['status']=='CLOSED','NOT_CLOSED_NO_RAW:'+str(closed['errors']))
    metadata=metadata_gate(root,args.group)
    out=HERE/'audit'/(args.group+'_INDEPENDENT_CONTINUOUS_C4_V1');out.mkdir(exist_ok=False)
    counts=dict(group=args.group,common_complete_audit_entered=0,common_complete_audit_returned=0,
        partial_original_evaluator_entered=0,partial_original_evaluator_returned=0,new_model_fit_predict_physics=0)
    new(out/'START.json',dict(status='CLOSED_METADATA_GATES_PASSED',source_sha256=sha(__file__),approval_sha256=args.approval_sha256,
        fixed_deadline_monotonic=deadline,closure=closed,C4_metadata=metadata,counts=counts))
    def log(value):
        with (out/'PROGRESS.jsonl').open('a') as stream:stream.write(json.dumps(common.clean(value),allow_nan=False)+'\n')
    try:
        counts['common_complete_audit_entered']+=1
        result=common.audit(root,args.group,closed,log)
        counts['common_complete_audit_returned']+=1
        counts['complete_original_evaluator_returned_records']=sum('fresh_original_evaluator' in row for row in result['trials'])
        result['C4_partial_original_replay']=partial_original_scoring(root,result,common,counts)
        counts['all_original_evaluator_returned_records']=counts['complete_original_evaluator_returned_records']+counts['partial_original_evaluator_returned']
        result['C4_registered_role_coverage']=role_coverage(args.group,closed,result)
        result['C4_actual_nonzero_reference']=actual_modal_reference_review(root,args.group,result)
        for item in result['C4_actual_nonzero_reference']:result['errors'].extend(item['errors'])
        result['C4_stored_BO_review']=stored_bo_review(root,args.group,result)
        result['errors'].extend(result['C4_stored_BO_review']['errors'])
        result['original_generic_limitation_records']=result.pop('limitations')
        result.update(scope='ORIGINAL_TWO_NEW_PARAMETER_CONDITIONS_FROZEN_ADAPTIVE_PROCEDURE_VALIDATION_NOT_CLINICAL_OR_BYTE_BLIND',
            original_case_metadata=metadata,counts=counts,status='C4_INDEPENDENT_CLOSED_AUDIT_PASS' if not result['errors'] else 'C4_INDEPENDENT_REVIEW_REQUIRED',
            task_boundary_scope='Actual14registeredTASKroles+2boundaries; gatedNOTRUN/aliases/optionalBOreported, never forced complete',
            prior_limitation='Fixed heterogeneous nominal earlyH150 + light lateH150 donors; not identical fullrecipes or unconditional value labels',
            audit_source_sha256=sha(__file__),original_common_audit_function_source_sha256=COMMON_SHA,
            wall_s=time.monotonic()-start,CPU_s=time.process_time()-cpu,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        new(out/'RESULT.json',common.clean(result));new(out/'END.json',dict(status=result['status'],result_sha256=sha(out/'RESULT.json'),counts=counts,
            wall_s=result['wall_s'],CPU_s=result['CPU_s'],RSS_KiB=result['RSS_KiB'],new_model_fit_predict_physics=0))
    except BaseException as error:
        new(out/'FAILED_PRESERVED.json',dict(status='FAILED_READONLY_PAID_PROGRESS_RETAINED_NO_RETRY',error_type=type(error).__name__,error=str(error),counts=counts,
            wall_s=time.monotonic()-start,CPU_s=time.process_time()-cpu,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            raw_coverage_not_completed_not_imputed=True,scorer_or_raw_work_after_last_durable_progress='UNKNOWN_NOT_ZERO',new_model_fit_predict_physics=0))
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0.)


if __name__=='__main__':main()
