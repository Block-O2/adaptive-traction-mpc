"""Materialize immutable job documents from a current or pending checkpoint.

Does not create an environment or launch a process. New runtime case files are
installed once, only after all four stock jobs and persistent B engineering
have closed. The main agent separately runs original prepare/supervise tools.
"""
from pathlib import Path
import argparse,copy,hashlib,json,os,time,re
P=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_new(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as stream:json.dump(obj,stream,indent=2,allow_nan=False);stream.write('\n')
def closed(group,expected_status='PASS_EXECUTED_WITH_REPORTED_QUALIFICATIONS'):
    e=load(P/'owned'/(group+'_SUPERVISOR_END.json'))
    assert e['state']=='STOP' and not e['survivors']
    if expected_status is not None:assert e['worker_exit_code']==0
    assert (P/'owned'/(group+'_EXIT.json')).is_file()
    done=load(P/'jobs'/group/'WORKER_DONE.json')
    if expected_status is not None:assert done['status']==expected_status
def install_cases():
    for group in ['V8CTX01','V8CTX02','V8CTX03','V8CTX04']:closed(group)
    closed('V8PERSISTB01',None)
    gate=load(P/'audit/PERSISTENT_B_MAIN_REVIEW_V1.json')
    assert gate['runtime_case_install_authorized_after_closure'] is True, 'PRIOR_OWNER_CLOSURE_MUST_BE_REVIEWED'
    contract=load(P/'freeze/V8_NEW_PARAMETER_CONDITIONS_V1.json'); records=[]
    for case in contract['cases']:
        source=P/case['payload_relative_path'];assert sha(source)==case['payload_sha256']
        destination=P/'runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1'/(case['case_key']+'.json')
        if destination.exists():assert sha(destination)==case['payload_sha256']
        else:
            with destination.open('xb') as stream:stream.write(source.read_bytes())
        records.append({'path':str(destination.relative_to(P)),'sha256':sha(destination)})
    audit=P/'audit/ONPOLICY_RUNTIME_CASE_INSTALL_V1.json'
    if not audit.exists():write_new(audit,{'status':'EXACT_FROZEN_PAYLOADS_INSTALLED_AFTER_ALL_PRIOR_OWNERS_CLOSED','cases':records,'unix':time.time(),'physics':0})

def prepare_job(run,group,context,first_pending_path=None):
    identity=load(run/'RUN_IDENTITY.json');contract_path=P/identity['approved_contract_path'];contract=load(contract_path)
    assert sha(contract_path)==identity['approved_contract_sha256']
    assert contract['status']=='APPROVED_BY_MAIN_AGENT' and contract['activation']==load(P/'ACTIVATION.json')['activation_id']
    assert time.time()<contract['global_deadline_unix']
    assert re.fullmatch(r'[A-Za-z0-9_]{1,120}',group) and not (P/'experiments'/(group+'.json')).exists()
    assert not (P/'jobs'/group).exists()
    for relative,expected in contract['frozen_dependencies'].items():
        assert sha(P/relative)==expected,'APPROVED_DEPENDENCY_CHANGED_BEFORE_PHYSICS:'+relative
    assert time.time()<identity['local_stop_unix']-contract['minimum_job_start_reserve_s']
    route=load(P/'freeze/ONPOLICY_V1_CASE_ROUTES.json')['development_routes'][context]
    config=copy.deepcopy(load(P/'experiments/V8CTX01.json'))
    for key in ['value_bundle','simple_control_bundle','policy_checkpoints','history_snapshot','holdout_protocol','holdout_protocol_sha256']:config.pop(key,None)
    config.update(group=group,mode='development',worker='v8_worker_v2.py',algorithm='v8_onpolicy_sequence_v1',actions=[],case_key=route['case_key'],case_sha256=route['case_sha256'],case_path='runtime/source/stages/stage5_personalized_motion_learning/configs/high_rom_v1/'+route['case_key']+'.json',local_stop_unix=identity['local_stop_unix'],job_wall_cap_s=1800,historical_repeats={})
    config['condition']['seed']=route['seed'];config['condition']['name']=group
    config['condition']['scope']='New frozen virtual parameter instance; same original task/equations/guard. Actor receives only actual causal commissioning25.'
    dependencies=copy.deepcopy(contract['frozen_dependencies'])
    dependencies[str(contract_path.relative_to(P))]=sha(contract_path)
    dependencies[config['case_path']]=sha(P/config['case_path'])
    assert dependencies[config['case_path']]==route['case_sha256']
    arm_inputs=[]
    if first_pending_path is None:
        current=load(run/'CURRENT.json')
        arm_inputs=[{'arm_id':arm,'snapshot_path':info['path'],'snapshot_sha256':info['sha256']} for arm,info in current['checkpoints'].items()]
        arm_inputs.sort(key=lambda item:contract['arm_ids'].index(item['arm_id']))
    else:
        first=load(first_pending_path);closed(first['job_group_evaluation_only'])
        assert first['stage']=='ALL_CURRENT_CONTEXT_SAMPLES_COLLECTED_NO_UPDATE'
        assert first['development_context_id_evaluation_only']!=context
        path=run/'pending_inputs'/group;path.mkdir(parents=True,exist_ok=False)
        for arm in contract['arm_ids']:
            dest=path/(arm+'.json');write_new(dest,first['snapshots'][arm])
            arm_inputs.append({'arm_id':arm,'snapshot_path':str(dest.relative_to(P)),'snapshot_sha256':sha(dest)})
        write_new(path/'SOURCE.json',{'original_pending_path':str(first_pending_path.relative_to(P)),'original_pending_sha256':sha(first_pending_path),'all_weights_unupdated':True})
    for item in arm_inputs:
        assert sha(P/item['snapshot_path'])==item['snapshot_sha256'];dependencies[item['snapshot_path']]=item['snapshot_sha256']
        snapshot=load(P/item['snapshot_path']);assert snapshot['local_stop_unix']==identity['local_stop_unix']
    config['onpolicy_sampling']={'schema':'v8.onpolicy_sampling_job.v1','development_context_id':context,'case_route_manifest':'freeze/ONPOLICY_V1_CASE_ROUTES.json','approved_contract_path':str(contract_path.relative_to(P)),'approved_contract_sha256':sha(contract_path),'receipt_adapter_path':'source/v8_onpolicy_receipt_adapter_v1.py','receipt_adapter_sha256':sha(P/'source/v8_onpolicy_receipt_adapter_v1.py'),'menu_path':contract['menu_path'],'menu_sha256':sha(P/contract['menu_path']),'arm_inputs':arm_inputs,'output_directory':str((run/'sampling'/group).relative_to(P))}
    config['frozen_artifacts']=dependencies
    write_new(P/'experiments'/(group+'.json'),config)
    return {'config':'experiments/'+group+'.json','sha256':sha(P/'experiments'/(group+'.json')),'environment_created':False,'physics_started':False}

def bind_pending(first_group,second_group,destination):
    for group in [first_group,second_group]:closed(group)
    config=load(P/'experiments'/(second_group+'.json'))
    source=P/config['onpolicy_sampling']['output_directory']/'PENDING_CHECKPOINTS.json'
    write_new(destination,{'schema':'v8.root_bound_two_job_pending.v1','root_expected_sampling_groups':[first_group,second_group],'original_final_pending_path':str(source.relative_to(P)),'original_final_pending_sha256':sha(source),'created_unix':time.time()})

def main():
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['install','job','bind']);p.add_argument('--run');p.add_argument('--group');p.add_argument('--context');p.add_argument('--first-pending');p.add_argument('--first-group');p.add_argument('--second-group');p.add_argument('--destination');a=p.parse_args()
    assert time.time()<load(P/'ACTIVATION.json')['hard_stop_unix']
    if a.operation=='install':install_cases();print('CASE_INSTALL_PASS_NO_PHYSICS')
    elif a.operation=='job':print(json.dumps(prepare_job(P/a.run,a.group,a.context,P/a.first_pending if a.first_pending else None)))
    else:bind_pending(a.first_group,a.second_group,P/a.destination);print('EXACT_PENDING_BOUND_NO_UPDATE')
if __name__=='__main__':main()
