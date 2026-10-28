"""只合并已审因果payload和既有A2训练标签；0fit/forward/physics。"""
from pathlib import Path
import copy
import hashlib
import json

P=Path('/home/hank/ihear-lab/deep_learning_method_exploration_v8')
OUT=P/'families/critic_value/coverage_state_v3'
BASE='runtime/source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/'
SOURCE_ROLES={'capture':'source/v7_causal_context.py','runtime':BASE+'full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py',
    'observer':BASE+'controller_interface.py','observation_contract':BASE+'task_observation.py',
    'history_guard':'source/v6_features.py','runtime_loader':'runtime/code/study_common.py'}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def main():
    a2=P/'families/critic_value/coverage_risk_v2/data/ACTUAL_COVERAGE_DATASET_V1.json'
    assert hashlib.sha256(a2.read_bytes()).hexdigest()=='e7a54dd7d3d39f0ab94cec45ceea284d6efec51d186ab74e46ff2335e82b79e0'
    old=json.loads(a2.read_text())
    audited=json.loads((OUT/'data/SCOPED_OUT0_STATES_V1.json').read_text())
    contexts={};profiles=[];paths=[];sources={}
    for record in audited['records']:
        group=record['group_evaluation_only'];package=P if group.startswith('V8CTX') else P.parent/'autonomous_learning_smoothness_v7'
        config=json.loads((package/'experiments'/(group+'.json')).read_text())
        frozen=json.loads((package/'jobs'/group/'SOURCE_MANIFEST.json').read_text())['files']
        mapping={**SOURCE_ROLES,'callback':'source/'+config['worker']}
        proof={}
        for role,relative in mapping.items():
            path=package/relative;actual=hashlib.sha256(path.read_bytes()).hexdigest()
            assert frozen[relative]==actual,(group,relative)
            proof[role]=actual;sources[str(path)]={'sha256':actual}
        if proof not in profiles:profiles.append(proof);paths.append(mapping)
        path=Path(record['source_payload_path']);raw=json.loads(path.read_text())
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['source_payload_file_sha256']
        contexts[group]={'raw_payload':raw,'source_proof':proof}
        sources[str(path)]={'sha256':record['source_payload_file_sha256']}
    # future driver须由owner对实际加载文件逐role计算SHA；不允许仅自称已验。
    mapping={**SOURCE_ROLES,'callback':'source/v8_worker_v2.py'}
    future={role:hashlib.sha256((P/relative).read_bytes()).hexdigest() for role,relative in mapping.items()}
    if future not in profiles:profiles.append(future);paths.append(mapping)
    rows=[]
    for original in old['rows']:
        row=copy.deepcopy(original);row['context']=contexts[row['group']];rows.append(row)
    label_identity=lambda records:digest([{'id':r['id'],'recipe':r['action_recipe_sha256'],'labels':r['labels_evaluation_only'],'parent':r['split_parent_group_evaluation_only']} for r in records])
    assert label_identity(rows)==label_identity(old['rows'])
    out={**old,'schema':'v8.a3.joined_scoped_state_labels.v1','rows':rows,'input_source_profiles':profiles,
        'input_source_profile_paths':paths,'A2_label_identity_sha256':label_identity(rows),'only_changed_field':'context',
        'source_A2_data_sha256':hashlib.sha256(a2.read_bytes()).hexdigest(),
        'scoped_state_data_sha256':hashlib.sha256((OUT/'data/SCOPED_OUT0_STATES_V1.json').read_bytes()).hexdigest(),
        'representations':['25','KIN33','WRENCH39'],'legacy77_still_invalid':True,'TASK_history_missing_still_missing':True,
        'new_fit_or_forward_or_physics':0}
    target=OUT/'data/STATE_JOINED_DATASET_V1.json'
    with target.open('x') as f:json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    with (OUT/'data/JOINED_SOURCE_MANIFEST_V1.json').open('x') as f:json.dump({'files':sources,'data_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'label_identity_sha256':out['A2_label_identity_sha256'],'new_fit_or_forward_or_physics':0},f,indent=2);f.write('\n')
    print(json.dumps({'data_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'label_identity_sha256':out['A2_label_identity_sha256'],'source_profiles':len(profiles),'rows':len(rows)}))


if __name__=='__main__':main()
