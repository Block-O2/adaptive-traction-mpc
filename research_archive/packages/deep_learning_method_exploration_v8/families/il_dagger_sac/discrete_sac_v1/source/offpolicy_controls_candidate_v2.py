"""SOURCE_ONLY: 25D同数据权限固定/if/nearest；未知动作无补标签。"""
import math


def reward_table(records):
    cells={}
    for r in records:
        key=(r['split_case_sha256_evaluation_only'],r['action_index'])
        cells.setdefault(key,[]).append(r['canonical_terminal_return'])
    return {key:sum(values)/len(values) for key,values in cells.items()}


def features_by_case(records):
    result={}
    for r in records:
        key=r['split_case_sha256_evaluation_only']
        if key in result:assert result[key]==r['features'],'CASE_HAS_MULTIPLE_CAUSAL_CONTEXTS_REQUIRES_EXPLICIT_NEW_CONTRACT'
        result[key]=r['features']
    return result


def best(cases,table):
    values=[]
    for action in range(5):
        if all((c,action) in table for c in cases):values.append((sum(table[c,action] for c in cases)/len(cases),action))
    if not values:return None
    return max(values,key=lambda v:(v[0],-v[1]))


def fit_controls(records,normalization):
    table=reward_table(records);features=features_by_case(records);cases=sorted(features)
    chosen=best(cases,table);assert chosen is not None,'NO_COMMON_FULLY_OBSERVED_FIXED_ACTION'
    stump={'feature_index':None,'threshold':None,'left_action':chosen[1],'right_action':chosen[1],'training_case_mean_reward':chosen[0]}
    candidates=0
    for j in range(25):
        values=sorted({features[c][j] for c in cases})
        for a,b in zip(values,values[1:]):
            threshold=(a+b)/2;left=[c for c in cases if features[c][j]<=threshold];right=[c for c in cases if features[c][j]>threshold]
            if min(len(left),len(right))<2:continue
            la,ra=best(left,table),best(right,table)
            if la is None or ra is None:continue
            candidates+=1;score=(la[0]*len(left)+ra[0]*len(right))/len(cases)
            if score>stump['training_case_mean_reward']+1e-12:
                stump={'feature_index':j,'threshold':threshold,'left_action':la[1],'right_action':ra[1],'training_case_mean_reward':score}
    nearest=[]
    for c in cases:
        actions=[(table[c,a],a) for a in range(5) if (c,a) in table]
        nearest.append({'case_sha256_evaluation_only':c,'features':features[c],'action_index':max(actions,key=lambda v:(v[0],-v[1]))[1]})
    return {'schema':'v8.sac_same_permission_controls.v2','normalization':normalization,'best_fixed_action':chosen[1],'stump':stump,'nearest':nearest,
       'training_case_count':len(cases),'candidate_stump_count':candidates,'rule_permission':'observed training-case outcomes only; action must be observed in every training case of its leaf','missing_labels_never_imputed':True}


def predict_control(bundle,features,control):
    assert len(features)==25 and all(math.isfinite(v) for v in features)
    if control=='CONSTANT_B':return {'action_index':0,'reason':'ORIGINAL_B'}
    if control=='BEST_FIXED':return {'action_index':bundle['best_fixed_action'],'reason':'TRAINING_CASE_BALANCED_BEST_FIXED'}
    if control=='IF_STUMP':
        s=bundle['stump'];left=s['feature_index'] is None or features[s['feature_index']]<=s['threshold']
        return {'action_index':s['left_action'] if left else s['right_action'],'reason':'FROZEN_SINGLE_IF'}
    assert control=='NEAREST';norm=bundle['normalization']
    def distance(row):return sum(((a-b)/s)**2 for a,b,s in zip(features,row['features'],norm['scale']))/25
    row=min(bundle['nearest'],key=lambda r:(distance(r),r['case_sha256_evaluation_only']))
    return {'action_index':row['action_index'],'reason':'NEAREST_TRAINING_CASE','RMS_distance':math.sqrt(distance(row))}
