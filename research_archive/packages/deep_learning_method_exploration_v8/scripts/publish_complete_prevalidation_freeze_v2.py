"""Root metadata publication after exposed integration, before new physics.

No candidate module, inference, fit, scorer, RNG, or physics is imported.
Actual endpoint inventories and all operative source files must already exist.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import resource
import signal
import time

P=Path(__file__).resolve().parents[1]
F='families/ppo_reward/continuous_scale_v1/'
HC='families/history_conditioned/'
MASTER='freeze/COMPLETE_MODEL_PROCEDURE_PREVALIDATION_MASTER_V1.json'
PROCEDURE='freeze/C4_NEW_PARAMETER_PROCEDURE_MAIN_AUTHORITY_V1.json'
APPROVAL='freeze/C4_VALIDATION_METADATA_BUILD_MAIN_APPROVAL_V3.json'


def sha(relative):return hashlib.sha256((P/relative).read_bytes()).hexdigest()
def load(relative):return json.loads((P/relative).read_text())
def ref(relative,**annotation):return dict(path=relative,sha256=sha(relative),**annotation)


def new(relative,value):
    with (P/relative).open('x') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--beta-inventory',required=True);ap.add_argument('--beta-inventory-sha256',required=True)
    ap.add_argument('--integration-review',required=True);ap.add_argument('--integration-review-sha256',required=True)
    args=ap.parse_args();started=time.monotonic();cpu=time.process_time()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824));resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('MASTER_METADATA_CAP')));signal.alarm(60)
    assert time.time()<1793112340.0-3600
    assert sha(args.beta_inventory)==args.beta_inventory_sha256
    assert sha(args.integration_review)==args.integration_review_sha256
    integration=load(args.integration_review)
    assert integration['group']=='V8FROZENENG01' and integration['all_owned_closed'] is True
    assert integration['read_only_model_identity_and_inference_review_pass'] is True
    assert integration['new_parameter_outcome_used_for_repair_or_selection'] is False
    routes=load('freeze/ONPOLICY_V1_CASE_ROUTES.json')['sealed_validation']
    parameter_shas={item['payload_sha256'] for item in routes}
    for raw in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines():
        event=json.loads(raw)
        if event.get('event')=='START' and event.get('group'):
            assert load('experiments/'+event['group']+'.json').get('case_sha256') not in parameter_shas,'NEW_PARAMETER_PHYSICS_ALREADY_OPENED'
    draft_rel=HC+'audit/DRAFT_ROOT_MASTER_INVENTORY_REFERENCES_V2.json'
    draft=load(draft_rel);pins=copy.deepcopy(draft['frozen_artifacts'])
    def pin(relative,expected=None):
        assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
        assert not any(part.upper() in ('CURRENT','CURRENT.JSON') for part in Path(relative).parts)
        assert (P/relative).resolve().is_relative_to(P)
        actual=sha(relative);assert expected is None or expected==actual,relative
        assert relative not in pins or pins[relative]==actual,relative
        pins[relative]=actual
    for group in ['V8FROZENENG01','V8VAL01','V8VAL02','V8FMEAN01','V8FMEAN02']:
        path='experiments/'+group+'.json';config=load(path)
        for relative,expected in config['frozen_artifacts'].items():pin(relative,expected)
        pin(path)
    beta=load(args.beta_inventory)
    models=copy.deepcopy(draft['model_inventory'])
    models['Beta_parent_first_last']=[ref(args.beta_inventory,role='ALL_COMMITTED_PARENT_FIRST_LAST_PLUS_SEPARATE_QUARANTINE')]
    for role in beta['roles']:
        for item in role['checkpoints']:
            pin(item['path'],item['sha256'])
            models['Beta_parent_first_last'].append(ref(item['path'],role=role['role'],arm_id=item['arm_id'],generation_index=role['generation_index']))
    feasibility='freeze/FEASIBILITY_FOUR_MEAN_ACTUAL_INVENTORY_V1.json'
    models['feasibility_counterfactual'].append(ref(feasibility,role='ALL_FOUR_FIXED_FINAL_ENDPOINTS_NO_BEST_SELECTION'))
    superseded={'source/v8_comparative_validation_v5.py',F+'comparative_composer_v4_candidate_v3.py',
                F+'beta_frozen_mean_extension_candidate_v1.py','scripts/prepare_frozen_comparison_v4_v4.py'}
    procedures=[item for item in draft['procedure_inventory'] if item['path'] not in superseded]
    for relative in ['source/v8_comparative_validation_v6.py',F+'comparative_composer_v4_candidate_v4.py',
                     F+'beta_frozen_mean_extension_candidate_v2.py','scripts/prepare_frozen_comparison_v4_v6.py',
                     'source/v8_frozen_feasibility_meanonly_v1.py','scripts/prepare_feasibility_four_mean_frozen_v2.py',
                     F+'feasibility_counterfactual_v1/frozen_mean_deployment_v1/EXPERIMENT_CONTRACT_SOURCE_ONLY_V1.json',
                     'freeze/FEASIBILITY_FOUR_MEAN_NEW_PARAMETER_REGISTRATION_V1.json',
                     'freeze/FEASIBILITY_FOUR_MEAN_ENDPOINT_MAIN_REVIEW_V1.json','freeze/FEASIBILITY_FOUR_MEAN_MAIN_AUTHORIZATION_V1.json',
                     str(Path(__file__).relative_to(P))]:
        pin(relative);procedures.append(ref(relative,role='OPERATIVE_PREVALIDATION_SOURCE_OR_PROCEDURE'))
    strong=copy.deepcopy(draft['strong_control_inventory'])
    strong.append(ref(F+'feasibility_counterfactual_v1/diagnostics/GATEC_ONCE_V1/RESULT.json',
        role='ALL_THREE_PREVIOUSLY_FITTED_SAME_AXIS_LINEAR_RULES_FIXED_LAMBDA1_ZERO_REFIT'))
    for relative in [draft_rel,args.beta_inventory,args.integration_review,'audit/FEASIBILITY_FOUR_MEAN_METADATA_BUILD_END_V1.json']:
        pin(relative)
    procedure_template_path=HC+'CONTINUOUS_V4_NEW_PROCEDURE_AUTHORITY_TEMPLATE_REVIEW_ONLY_V1.json'
    metadata_template_path=HC+'CONTINUOUS_VALIDATION_METADATA_BUILD_APPROVAL_TEMPLATE_REVIEW_ONLY_V3.json'
    pin(procedure_template_path,'5338c6c73780203312de00d27d1461ec3558570b45519e1a486cb13c6b8629df')
    pin(metadata_template_path,'a533498c3b70313df8dc0709182100b238e1d5bc2aa387215c827f7d56a61af8')
    procedure_template=load(procedure_template_path)
    metadata_template=load(metadata_template_path)
    assert procedure_template['C4_source_manifest_sha256']==sha(HC+'CONTINUOUS_V4_SOURCE_ONLY_MANIFEST_V1.json')
    assert procedure_template['wrapper_sha256']==sha('source/v8_continuous_ilc_worker_v4.py')
    assert procedure_template['family_worker_sha256']==sha(HC+'continuous_ilc_worker_v4.py')
    assert procedure_template['BO_contract_sha256']==sha(HC+'C2B_COMPONENT_BO_CONTRACT_V2.json')
    assert metadata_template['source_manifest_sha256']==sha(HC+'CONTINUOUS_VALIDATION_METADATA_BUILDER_SOURCE_MANIFEST_V3.json')
    assert metadata_template['contract_sha256']==sha(HC+'CONTINUOUS_VALIDATION_METADATA_BUILDER_CONTRACT_V3.json')
    for refs in [*models.values(),strong,procedures]:
        assert isinstance(refs,list) and refs
        for item in refs:pin(item['path'],item['sha256'])
    for relative,expected in list(pins.items()):pin(relative,expected)
    assert all(not (P/path).exists() for path in [MASTER,PROCEDURE,APPROVAL])
    master=dict(schema='v8.root_complete_model_procedure_freeze.v1',status='FROZEN_BEFORE_ANY_NEW_PARAMETER_PHYSICS',
        frozen_unix=time.time(),original_global_stop_unix=1793114740.0,frozen_artifacts=pins,model_inventory=models,
        strong_control_inventory=strong,procedure_inventory=procedures,
        root_semantic_completeness_review='Main reviewed all seven actual model containers, strong controls, operative deployments, and independent C4 frozen procedure. All fixed endpoints retained; no best selection.',
        exposed_integration_review=ref(args.integration_review),original_new_parameter_physics_starts=0,
        original_parameter_payloads_structurally_read_not_byte_blind=True,
        Beta_uncommitted_batch02='EXTERNAL_QUARANTINE_UNRESOLVED_PREFIX_UNKNOWN_NO_CANCEL_NO_COMMIT_NO_ENDPOINT_UPDATES',
        C4_scope='Frozen adaptive procedure; fit on its own earlier trials is separately counted and is not a frozen-weight policy.',
        global_model_or_episode_quota=None)
    new(MASTER,master)
    authority=copy.deepcopy(procedure_template)
    authority.update(status='ROOT_APPROVED_C4_NEW_PARAMETER_PROCEDURE_RUNTIME_BO_V1',approved_unix=time.time(),
        root_inventory_path=MASTER,root_inventory_sha256=sha(MASTER),continuous_ilc_physics_authorized=True,
        c2b_component_bo_v2_fit_authorized=True,c2b_component_bo_v2_candidate_physics_authorized=True,
        physics_dispatch_authorized=False)
    new(PROCEDURE,authority)
    approval=copy.deepcopy(metadata_template)
    approval.update(status='ROOT_APPROVED_METADATA_BUILD_ONLY_V2',approved_unix=time.time(),root_inventory_path=MASTER,
        root_inventory_sha256=sha(MASTER),procedure_approval_path=PROCEDURE,procedure_approval_sha256=sha(PROCEDURE),
        root_inventory_completeness_review_pass=True,new_parameter_preoutcome_freeze_review_pass=True,physics_dispatch_authorized=False)
    new(APPROVAL,approval)
    new('audit/COMPLETE_PREVALIDATION_FREEZE_PUBLICATION_END_V1.json',dict(status='PUBLISHED_METADATA_ONLY',
        created_unix=time.time(),outputs={relative:sha(relative) for relative in [MASTER,PROCEDURE,APPROVAL]},
        frozen_artifacts_count=len(pins),family_reference_counts={key:len(value) for key,value in models.items()},
        wall_s=time.monotonic()-started,cpu_s=time.process_time()-cpu,model_imports=0,inference=0,fit=0,physics=0))
    print(json.dumps(dict(master=ref(MASTER),procedure_authority=ref(PROCEDURE),metadata_approval=ref(APPROVAL))),flush=True)


if __name__=='__main__':main()
