"""SOURCE_ONLY：新只读授权下固定权重前向；不导入训练head，无step/fit。"""
import copy
import hashlib
import json
import math
import time

STOP=1793114740.
SEEDS=(20261027101,20261027102,20261027103)
ARCHS=('TANH16','LINEAR')
ENDS=(0,25,200)
TARGETS=('RETURN','RISK','JF_FIXED','JM_FIXED','JF_CENTERED','JM_CENTERED')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def key(seed,arch,target,endpoint):return f'{seed}/{arch}/{target}/E{endpoint:04d}'


def authorized(a):
    assert a['schema']=='v8.neuralq.readonly_fixed_models_authorization.v3'
    assert a['status']=='APPROVED_BY_MAIN_AGENT_FOR_NEURALQ_READ_ONLY_FIXED_MODELS_V3'
    assert a['scope'] in ('READ_ONLY_FROZEN_OUT0','READ_ONLY_KNOWN_REPLAY_PARITY')
    assert a['approved_unix']<=time.time()<min(a['expires_unix'],STOP) and a['expires_unix']<=STOP
    assert a['training_or_physics_authorized'] is False


def required_heads():
    ids=[]
    for endpoint in ENDS:
        for seed in SEEDS:
            for arch in ARCHS:
                ids.extend(key(seed,arch,target,endpoint) for target in ('RETURN','RISK'))
                if endpoint==200:ids.extend(key(seed,arch,target,endpoint) for target in TARGETS[2:])
    assert len(ids)==60 and len(set(ids))==60
    return ids


def selector_inventory():
    labels=[]
    for endpoint in ENDS:
        for seed in SEEDS:
            for arch in ARCHS:
                prefix=f'NQ_{arch}_S{seed}_E{endpoint:04d}'
                labels.extend(prefix+'_RETURN_'+risk for risk in ('RISKOFF','RISKON'))
                if endpoint==200:
                    for target in ('JF_FIXED','JF_CENTERED'):labels.extend(prefix+'_'+target+'_'+risk for risk in ('RISKOFF','RISKON'))
    for target in ('RETURN','JF_CENTERED'):
        labels.append('NQ_RIDGE_'+target+'_RISKOFF')
        labels.extend(f'NQ_RIDGE_{target}_RISKON_LINEAR_S{seed}_E0200' for seed in SEEDS)
    assert len(labels)==68 and len(set(labels))==68
    return labels


def restore_fixed(document,*,authority,expected_bundle_object_sha256,expected_source_manifest_sha256,accounting=None):
    """一次batch=60head+3ridge逻辑restore；63次deepcopy，不创建随机模型。"""
    accounting={} if accounting is None else accounting
    authorized(authority)
    assert authority['bundle_object_sha256']==document['bundle_object_sha256']==expected_bundle_object_sha256
    assert digest(document['bundle'])==expected_bundle_object_sha256
    assert authority['source_manifest_sha256']==expected_source_manifest_sha256
    b=document['bundle'];assert b['schema']=='v8.neuralq.readonly_all_full_fixed_models.v3'
    assert b['primary']=='TANH16/RETURN_GREEDY/FINAL200/all3seeds individually'
    assert len(b['heads'])==108 and len(b['ridge'])==3 and len(b['feature_names'])==25
    assert digest(b['feature_names'])==authority['feature_names_sha256']
    assert len(b['action_contracts'])==5 and [digest(r) for r in b['action_contracts']]==b['full_recipe_sha256']==authority['full_recipe_sha256']
    import numpy as np
    assert np.__version__==authority['expected_numpy_version']
    n=b['input_normalization'];mean=np.asarray(n['mean'],dtype=float);scale=np.asarray(n['scale'],dtype=float)
    assert mean.shape==scale.shape==(25,) and np.isfinite(mean).all() and np.isfinite(scale).all() and (scale>0).all()
    models={};parameter_arrays=0
    for mid in required_heads():
        accounting['model_restore_entry']=accounting.get('model_restore_entry',0)+1
        accounting['logical_model_deepcopy_entry']=accounting.get('logical_model_deepcopy_entry',0)+1
        m=copy.deepcopy(b['heads'][mid])
        accounting['logical_model_deepcopy_completed']=accounting.get('logical_model_deepcopy_completed',0)+1
        assert mid==key(m['seed'],m['architecture'],m['target'],m['endpoint'])
        shapes={'W':(25,5),'b':(5,)} if m['architecture']=='LINEAR' else {'W1':(25,16),'b1':(16,),'W2':(16,5),'b2':(5,)}
        assert set(m['params'])==set(shapes)
        for name,shape in shapes.items():
            m['params'][name]=np.asarray(m['params'][name],dtype=float);parameter_arrays+=1
            assert m['params'][name].shape==shape and np.isfinite(m['params'][name]).all()
        on=m['output_normalization'];assert math.isfinite(on['mean']) and math.isfinite(on['scale']) and on['scale']>0
        if m['target'] in ('RETURN','RISK'):assert on=={'mean':0.,'scale':1.}
        models[mid]=m
        accounting['model_restore_completed']=accounting.get('model_restore_completed',0)+1
    ridge={}
    for target in ('RETURN','JF_CENTERED','JM_CENTERED'):
        accounting['model_restore_entry']=accounting.get('model_restore_entry',0)+1
        accounting['logical_model_deepcopy_entry']=accounting.get('logical_model_deepcopy_entry',0)+1
        m=copy.deepcopy(b['ridge'][target])
        accounting['logical_model_deepcopy_completed']=accounting.get('logical_model_deepcopy_completed',0)+1
        assert m['target']==target and len(m['coefficients'])==5
        for i,coef in enumerate(m['coefficients']):
            assert coef is not None
            m['coefficients'][i]=np.asarray(coef,dtype=float);parameter_arrays+=1
            assert m['coefficients'][i].shape==(26,) and np.isfinite(m['coefficients'][i]).all()
        on=m['output_normalization'];assert math.isfinite(on['mean']) and math.isfinite(on['scale']) and on['scale']>0
        ridge[target]=m
        accounting['model_restore_completed']=accounting.get('model_restore_completed',0)+1
    assert parameter_arrays==195
    accounting['completed_parameter_array_constructions']=parameter_arrays
    accounting['completed_input_normalization_array_constructions']=2
    return {'schema':'v8.neuralq.restored_readonly_batch.v3','models':models,'ridge':ridge,'mean':mean,'scale':scale,
            'feature_names':b['feature_names'],'bundle_object_sha256':expected_bundle_object_sha256,
            'source_manifest_sha256':expected_source_manifest_sha256,
            'restore_counts':{'logical_model_restores':63,'logical_model_deepcopies':63,'parameter_array_constructions':195,'input_normalization_arrays':2,'random_initialization_fit_gradient':0}}


def predict_fixed(restored,feature_names,commissioned25,*,qa_validated,authority,accounting=None):
    """一真实context：60head+3ridge forwards，68选择；JF目标独立，JM仅诊断。"""
    accounting={} if accounting is None else accounting
    authorized(authority)
    assert qa_validated is True and list(feature_names)==restored['feature_names']
    assert restored['bundle_object_sha256']==authority['bundle_object_sha256'] and restored['source_manifest_sha256']==authority['source_manifest_sha256']
    import numpy as np
    x=np.asarray(commissioned25,dtype=float);assert x.shape==(25,) and np.isfinite(x).all()
    z=((x-restored['mean'])/restored['scale']).reshape(1,25)
    values={};matrix_calls=0;tanh_calls=0;sigmoid_calls=0
    for mid,m in restored['models'].items():
        accounting['head_forward_entry']=accounting.get('head_forward_entry',0)+1
        p=m['params']
        if m['architecture']=='LINEAR':out=z@p['W']+p['b'];matrix_calls+=1
        else:
            h=np.tanh(z@p['W1']+p['b1']);out=h@p['W2']+p['b2'];matrix_calls+=2;tanh_calls+=1
        if m['target']=='RISK':
            e=np.exp(-np.abs(out));out=np.where(out>=0,1./(1.+e),e/(1.+e));sigmoid_calls+=1
        else:out=out*m['output_normalization']['scale']+m['output_normalization']['mean']
        assert np.isfinite(out).all();values[mid]=out[0].tolist()
        accounting['head_forward_completed']=accounting.get('head_forward_completed',0)+1
    zb=np.concatenate((z[0],np.ones(1)))
    for target,m in restored['ridge'].items():
        accounting['ridge_forward_entry']=accounting.get('ridge_forward_entry',0)+1
        vv=[]
        for coef in m['coefficients']:
            vv.append(float(zb@coef)*m['output_normalization']['scale']+m['output_normalization']['mean']);matrix_calls+=1
        assert all(math.isfinite(v) for v in vv);values['RIDGE/'+target]=vv
        accounting['ridge_forward_completed']=accounting.get('ridge_forward_completed',0)+1
    assert matrix_calls==105 and tanh_calls==30 and sigmoid_calls==18
    accounting['completed_matrix_products']=matrix_calls;accounting['completed_tanh']=tanh_calls;accounting['completed_sigmoid']=sigmoid_calls
    decisions={}
    def choose(label,target_values,risk_values,mode,objective):
        assert mode in ('RISKOFF','RISKON') and objective in ('RETURN_MAX','JF_MIN')
        allowed=list(range(5)) if mode=='RISKOFF' else [i for i,v in enumerate(risk_values) if v<=.1]
        if allowed:index=max(allowed,key=lambda i:(target_values[i],-i)) if objective=='RETURN_MAX' else min(allowed,key=lambda i:(target_values[i],i))
        else:index=0
        decisions[label]={'action_index':index,'objective':objective,'risk_mode':mode,'risk_threshold':.1,
                          'prediction_abstained':not bool(allowed),'execution_fallback_B_predeclared':not bool(allowed),
                          'reason':'FIXED_OBJECTIVE_WITH_INDEPENDENT_RISK' if allowed else 'B_FALLBACK_NO_ESTIMATED_LOW_RISK_ACTION',
                          'original_qualification_granted':False,'future_qualification_mask_used':False,
                          'JF_JM_weighted_score_used':False}
    for endpoint in ENDS:
        for seed in SEEDS:
            for arch in ARCHS:
                prefix=f'NQ_{arch}_S{seed}_E{endpoint:04d}';risk=values[key(seed,arch,'RISK',endpoint)]
                for mode in ('RISKOFF','RISKON'):choose(prefix+'_RETURN_'+mode,values[key(seed,arch,'RETURN',endpoint)],risk,mode,'RETURN_MAX')
                if endpoint==200:
                    for target in ('JF_FIXED','JF_CENTERED'):
                        for mode in ('RISKOFF','RISKON'):choose(prefix+'_'+target+'_'+mode,values[key(seed,arch,target,endpoint)],risk,mode,'JF_MIN')
    for target in ('RETURN','JF_CENTERED'):
        objective='RETURN_MAX' if target=='RETURN' else 'JF_MIN'
        choose('NQ_RIDGE_'+target+'_RISKOFF',values['RIDGE/'+target],[0.]*5,'RISKOFF',objective)
        for seed in SEEDS:choose(f'NQ_RIDGE_{target}_RISKON_LINEAR_S{seed}_E0200',values['RIDGE/'+target],values[key(seed,'LINEAR','RISK',200)],'RISKON',objective)
    assert list(decisions)==selector_inventory()
    authorized(authority)
    return {'schema':'v8.neuralq.readonly_batch_prediction.v3','decisions':decisions,'all_head_values':values,
            'primary_labels':[f'NQ_TANH16_S{s}_E0200_RETURN_RISKOFF' for s in SEEDS],
            'cost_variants':'JF_FIXED/JF_CENTERED final200; JM_FIXED/JM_CENTERED predictions diagnostic only, never mixed',
            'forward_counts':{'head_API':60,'ridge_API':3,'matrix_products':105,'tanh':30,'sigmoid':18,'scalar_outputs':315,'model_restores_extra':0,'model_deepcopies_extra':0,'new_training_or_physics':0}}
