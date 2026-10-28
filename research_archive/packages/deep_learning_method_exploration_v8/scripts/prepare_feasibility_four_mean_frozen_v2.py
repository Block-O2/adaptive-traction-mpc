"""Metadata only: freeze all four actual final feasibility policies and jobs."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import resource
import signal
import time

P = Path(__file__).resolve().parents[1]
F = 'families/ppo_reward/continuous_scale_v1/'
CF = F + 'feasibility_counterfactual_v1/'
HERE = CF + 'frozen_mean_deployment_v1/'
GROUPS = ['V8FMEAN01', 'V8FMEAN02']
POLICY_FIELDS = ('schema','feature_names','normalization','weights','axis_contract','axis_contract_sha256','seed','arm_id','gain','version')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def sha(relative):
    return hashlib.sha256((P / relative).read_bytes()).hexdigest()


def load(relative):
    return json.loads((P / relative).read_text())


def ref(relative):
    assert (P / relative).resolve().is_relative_to(P)
    return dict(path=relative, sha256=sha(relative))


def new(relative, value):
    with (P / relative).open('x') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--wrapper',required=True);parser.add_argument('--wrapper-sha256',required=True)
    args=parser.parse_args();started=time.monotonic();cpu=time.process_time()
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824))
    resource.setrlimit(resource.RLIMIT_CPU,(60,60))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('FOUR_MEAN_METADATA_CAP')))
    signal.alarm(60)
    assert args.wrapper.startswith('source/') and args.wrapper.endswith('.py') and sha(args.wrapper)==args.wrapper_sha256
    assert time.time() < load('runtime/RUN_PLAN.json')['dispatch_cutoff_unix']-1800
    static=load(HERE+'SOURCE_REQUIREMENTS_MANIFEST_V1.json')['known_static_sources_sha256']
    static=copy.deepcopy(static);static[args.wrapper]=args.wrapper_sha256
    for path,expected in static.items():assert sha(path)==expected,path
    metadata_inputs = {relative: sha(relative) for relative in (
        'experiments/V8COMPENG03.json', 'jobs/V8COMPENG03/SOURCE_MANIFEST.json',
        'freeze/ONPOLICY_V1_CASE_ROUTES.json', 'freeze/V8_NEW_PARAMETER_CONDITIONS_V1.json')}
    assert metadata_inputs['experiments/V8COMPENG03.json'] == load('jobs/V8COMPENG03/SOURCE_MANIFEST.json')['config_sha256'], 'ORIGINAL_CLOSED_BASE_CONFIG_CHANGED'
    assert sha(CF+'diagnostics/GATEC_ONCE_V1/RESULT.json')=='28bedbdffab0fee9f46723625fda0459bd3b0ce03194af780906392c71a6d044'
    assert sha(CF+'context_loo_v1/diagnostics/GATEL_ONCE_V1/RESULT.json')=='55369ef436e9b0b54023ee7cdb20e9c520d1933c2ed69f865bc3f7f011129db2'
    sources=[('GLOBAL',CF+'diagnostics/GATEC_ONCE_V1/'),('CONTEXT_LOO',CF+'context_loo_v1/diagnostics/GATEL_ONCE_V1/')]
    models=[];closed=[]
    for scope,directory in sources:
        result=load(directory+'RESULT.json');done=load(directory+'DONE.json')
        assert done['status']=='COMPLETED_EXACT_APPROVED_OFFLINE_STAGE' and done['result_sha256']==sha(directory+'RESULT.json')
        pid=done['final']['pid'];ticks=done['final']['start_ticks'];proc=Path('/proc')/str(pid)/'stat'
        current_ticks=int(proc.read_text().rsplit(')',1)[1].split()[19]) if proc.exists() else None
        assert current_ticks!=ticks,'ORIGINAL_OFFLINE_OWNER_STILL_ALIVE'
        closed.append(dict(scope=scope,pid=pid,original_start_ticks=ticks,current_start_ticks=current_ticks,closed=True))
        for algorithm,suffix,steps in [('REINFORCE','RF1',1),('PPO','PPO3',3)]:
            policy=result['private_policies'][algorithm]
            assert policy['counters']['parameter_updates']==steps and len(result['traces'][algorithm])==steps
            models.append(dict(label='FEAS_'+scope+'_'+suffix,closed_result=ref(directory+'RESULT.json'),
                closed_DONE=ref(directory+'DONE.json'),policy_json_path=['private_policies',algorithm],
                policy_sha256=digest({key:policy[key] for key in POLICY_FIELDS}),weights_sha256=digest(policy['weights'])))
    routes=load('freeze/ONPOLICY_V1_CASE_ROUTES.json')['sealed_validation']
    validation_shas={row['payload_sha256'] for row in routes}
    for raw in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines():
        event=json.loads(raw)
        if event.get('event')=='START' and event.get('group'):
            assert load('experiments/'+event['group']+'.json').get('case_sha256') not in validation_shas,'NEW_PARAMETER_PHYSICS_ALREADY_OPENED'
    registration_rel='freeze/FEASIBILITY_FOUR_MEAN_NEW_PARAMETER_REGISTRATION_V1.json'
    review_rel='freeze/FEASIBILITY_FOUR_MEAN_ENDPOINT_MAIN_REVIEW_V1.json'
    inventory_rel='freeze/FEASIBILITY_FOUR_MEAN_ACTUAL_INVENTORY_V1.json'
    auth_rel='freeze/FEASIBILITY_FOUR_MEAN_MAIN_AUTHORIZATION_V1.json'
    outputs=[registration_rel,review_rel,inventory_rel,auth_rel]+['experiments/'+group+'.json' for group in GROUPS]
    assert all(not (P/relative).exists() for relative in outputs)
    registration=dict(schema='v8.feasibility_four_mean_new_parameter_registration.v1',job_groups=GROUPS,
        created_unix=time.time(),original_task_and_equations_unchanged=True,original_registration=ref('freeze/V8_NEW_PARAMETER_CONDITIONS_V1.json'),
        conditions=[dict(group=group,case_key=route['case_key'],seed=route['seed'],payload=ref(route['payload_relative_path'])) for group,route in zip(GROUPS,routes)])
    new(registration_rel,registration)
    review=dict(schema='v8.frozen_feasibility_endpoint_freeze_review.v1',
        status='ALL_FOUR_FINAL_MODELS_AND_PROGRAM_FROZEN_BEFORE_NEW_PARAMETER_PHYSICS',frozen_unix=time.time(),
        original_global_stop_unix=1793114740.0,new_parameter_parents_not_started_at_freeze=True,
        outcome_or_best_endpoint_selection=False,source_files_sha256=static,models_object_sha256=digest(models),
        new_parameter_registration=ref(registration_rel),actual_offline_owner_closure=closed,
        original_validation_physics_start_count=0,payload_bytes_structurally_exposed_not_byte_blind=True,
        fixed_behavior_replay_not_fresh_onpolicy=True,all_four_models_evaluated_no_best_selection=True,
        source_review='Main read full adapter, sequence, contract and thin root wrapper; original three-value safety and original task remain exact.',
        metadata_builder=ref(str(Path(__file__).relative_to(P))),model_inference_or_fit_by_builder=0)
    new(review_rel,review)
    axis=ref(F+'FROZEN_AXIS_GATE1_V1.json')
    inventory=dict(schema='v8.frozen_feasibility_four_mean_inventory.v1',
        status='ALL_FOUR_ACTUAL_FIXED_FINAL_ENDPOINTS_FROZEN_NOT_BEST',models=models,
        main_endpoint_freeze_review=ref(review_rel),new_parameter_registration=ref(registration_rel),axis=axis,
        axis_object_sha256=digest(load(axis['path'])),original_recipe_menu=ref('freeze/ONPOLICY_FIVE_RECIPE_MENU_V1.json'),
        A3_adapter_manifest=ref('families/critic_value/coverage_state_v3/LIVE_SELECTOR_ADAPTER_MANIFEST_V1.json'),
        original_behavior_exact_export=ref(CF+'metadata_exports/ROOT_G0_CLOSED4_EXACT_V1/ORIGINAL_G0_RF_RAW_EXACT.json'),
        closed_global_result=ref(CF+'diagnostics/GATEC_ONCE_V1/RESULT.json'))
    new(inventory_rel,inventory)
    auth=dict(schema='v8.frozen_feasibility_mean_main_approval.v1',status='APPROVED_BY_MAIN_FOR_FOUR_FROZEN_MEANS_ONLY',
        inventory=ref(inventory_rel),authorized_job_groups=GROUPS,mean_forward_only=True,restore_fit_RNG_or_sampling=0,
        activation_sha256=sha('ACTIVATION.json'),approved_unix=time.time(),
        deployment_deadline_unix=load('runtime/RUN_PLAN.json')['physics_hard_stop_unix'],
        source_files_sha256=static,root_wrapper=ref(args.wrapper),physics_dispatch_authorized=False)
    new(auth_rel,auth)
    base=load('experiments/V8COMPENG03.json');deps=copy.deepcopy(base['frozen_artifacts']);deps.update(static)
    for relative,expected in metadata_inputs.items():
        assert relative not in deps or deps[relative] == expected, relative
        deps[relative] = expected
    needed=['ACTIVATION.json','runtime/RUN_PLAN.json',registration_rel,review_rel,inventory_rel,auth_rel,
            str(Path(__file__).relative_to(P)),HERE+'SOURCE_REQUIREMENTS_MANIFEST_V1.json',HERE+'EXPERIMENT_CONTRACT_SOURCE_ONLY_V1.json']
    needed += [item[key]['path'] for item in models for key in ('closed_result','closed_DONE')]
    needed += [inventory[key]['path'] for key in ('axis','original_recipe_menu','A3_adapter_manifest','original_behavior_exact_export','closed_global_result')]
    for route in routes:
        needed += [route['payload_relative_path'],'runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/'+route['case_key']+'.json']
    for relative in needed:
        value=sha(relative);assert relative not in deps or deps[relative]==value;deps[relative]=value
    for relative,expected in deps.items():assert sha(relative)==expected,relative
    menu={row['tag']:row for row in base['actions']}
    for group,route in zip(GROUPS,routes):
        config=copy.deepcopy(base)
        for key in ['comparative_validation','frozen_selectors','holdout_protocol','holdout_protocol_sha256','comparative_composer_v4','beta_mean_extension']:
            config.pop(key,None)
        config.update(group=group,algorithm=Path(args.wrapper).stem,worker='v8_worker_v2.py',mode='validation',
            actions=[copy.deepcopy(menu[tag]) for tag in ('B','EARLY_H150')],frozen_artifacts=copy.deepcopy(deps),
            historical_repeats={},job_wall_cap_s=1800,scientific_branch='FROZEN_FOUR_FEASIBILITY_MEANS_NEW_PARAMETER_VALIDATION')
        config['condition'].update(name=group,seed=route['seed'],split='FROZEN_NEW_PARAMETER_VALIDATION',
            role='All four fixed final global/LOO policies and strong B/H150/lambda1 control frozen before any new-parameter physics.',
            scope='Virtual new parameter condition; payload bytes structurally exposed, physical outputs unopened at freeze.')
        config['case_path']='runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/'+route['case_key']+'.json'
        config['case_sha256']=route['payload_sha256']
        config['frozen_feasibility_means']=dict(schema='v8.frozen_feasibility_mean_job.v1',inventory=ref(inventory_rel),deployment_authorization=ref(auth_rel))
        new('experiments/'+group+'.json',config)
    new('audit/FEASIBILITY_FOUR_MEAN_METADATA_BUILD_END_V1.json',dict(status='METADATA_COMPLETE_NO_MODEL_NO_PHYSICS',
        created_unix=time.time(),outputs={relative:sha(relative) for relative in outputs},
        wall_s=time.monotonic()-started,cpu_s=time.process_time()-cpu,model_imports=0,forwards=0,fit=0,new_physics=0))
    print(json.dumps(dict(status='FOUR_MODELS_AND_TWO_JOBS_FROZEN_NO_PHYSICS',inventory=ref(inventory_rel),
        configs={group:sha('experiments/'+group+'.json') for group in GROUPS},pins=len(deps))),flush=True)


if __name__=='__main__':
    main()
