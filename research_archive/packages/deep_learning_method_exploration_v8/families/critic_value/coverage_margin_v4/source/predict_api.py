"""A4纯预测source候选；未调用。原45margin保守门，三λmean成本。"""
import hashlib
import json
import math
from causal_api import to_context_full
from a3_reference_api import transform,design,dot,sigmoid,predict_control as a3_predict_control
LAMBDAS=[.1,1.,10.]
ELIGIBILITY=['CLASSIFIER39','SINGLE1_002','ENSEMBLE45_002','ENSEMBLE45_000','ENSEMBLE45_002_AND_CLASSIFIER']
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def source_context(bundle,raw,proof):return to_context_full(raw,bundle['input_source_profiles'],proof)
def _risk(bundle,spec,context,item,vector):
 if spec.get('risk_weights') is not None:return sigmoid(dot(vector,spec['risk_weights']))
 # 仅开发LOCO重用A3已冻预测；无原资格真值mask，未来live bundle必须有risk_weights。
 assert bundle.get('development_only') is True and bundle.get('diagnostic_context_vector_sha256')==digest(context['features'])
 return bundle['frozen_A3_LOCO_risk_by_recipe'][item['recipe_sha256']]
def predict(bundle,raw,cost_kind='ABS',eligibility='ENSEMBLE45_002',objective='JF_QUALIFIED',*,source_proof=None):
 assert bundle['schema']=='v8.a4.original_component_margin_bundle.v1' and eligibility in ELIGIBILITY
 assert cost_kind in ['ABS','DELTA_B'] and objective in ['JF_QUALIFIED','JM_QUALIFIED','STRICT_JM']
 context=source_context(bundle,raw,source_proof);spec=bundle['model'];z=transform(spec,context);menu=bundle['menu'];predictions=[]
 head=spec['cost_heads'][cost_kind];margin=spec['margin_head']
 assert head['lambdas']==margin['lambdas']==LAMBDAS
 for index,item in enumerate(menu):
  vector=design(z,index,len(menu));cost_estimates=[[dot(vector,[row[j] for row in weights])*head['target_scale'][j]+head['target_center'][j] for j in range(2)] for weights in head['weights']]
  mean=[sum(v[j] for v in cost_estimates)/3 for j in range(2)];spread=[(sum((v[j]-mean[j])**2 for v in cost_estimates)/3)**.5 for j in range(2)]
  if cost_kind=='DELTA_B' and item['tag']=='B':mean,spread=[0.,0.],[0.,0.]
  estimates=[[margin['target_center'][j] if j in margin['constant_target_positions'] else dot(vector,[row[j] for row in weights])*margin['target_scale'][j]+margin['target_center'][j] for j in range(45)] for weights in margin['weights']]
  lower=[min(v[j] for v in estimates) for j in range(45)];single=min(estimates[1]);worst=min(lower);critical=min(range(45),key=lambda j:(lower[j],j))
  points=spec['support_train_z'][index];distance=min((sum((a-b)**2 for a,b in zip(p,z))/len(z))**.5 for p in points) if points else None
  supported=len(points)>=bundle['minimum_support_contexts'] and distance is not None and distance<=bundle['distance_limit']
  risk=_risk(bundle,spec,context,item,vector)
  admitted={'CLASSIFIER39':risk<.5,'SINGLE1_002':single>=.02,'ENSEMBLE45_002':worst>=.02,'ENSEMBLE45_000':worst>=0.,'ENSEMBLE45_002_AND_CLASSIFIER':worst>=.02 and risk<.5}[eligibility]
  predictions.append({'tag':item['tag'],'recipe_sha256':item['recipe_sha256'],'predicted_JF_component':mean[0],'predicted_JM_component':mean[1],'ridge_spread_JF':spread[0],'ridge_spread_JM':spread[1],
   'cost_estimates_by_lambda':cost_estimates,'margin_estimates_by_lambda':estimates,'per_component_min_across_lambda':lower,'worst_margin':worst,'critical_component':bundle['component_names'][critical],
   'single_lambda1_worst_margin':single,'qualification_failure_score':risk,'supported':supported,'support_context_count':len(points),'nearest_train_RMS_distance':distance,'predicted_eligibility':admitted})
 baseline=next(r for r in predictions if r['tag']=='B')
 for row in predictions:
  row['predicted_delta_JF_vs_B']=row['predicted_JF_component']-baseline['predicted_JF_component'];row['predicted_delta_JM_vs_B']=row['predicted_JM_component']-baseline['predicted_JM_component']
 allowed=[r for r in predictions if r['supported'] and r['predicted_eligibility'] and (objective!='STRICT_JM' or r['predicted_delta_JM_vs_B']<=1e-12)]
 key='predicted_JM_component' if objective=='JM_QUALIFIED' else 'predicted_JF_component';chosen=min(allowed,key=lambda r:(r[key],r['tag'])) if allowed else None
 item=next(m for m in menu if m['recipe_sha256']==chosen['recipe_sha256']) if chosen else None
 return {'schema':'v8.a4.margin_decision.v1','method':eligibility,'cost_kind':cost_kind,'objective':objective,'input_representation':'WRENCH39','cost_aggregation':'ARITHMETIC_MEAN_SAME_THREE_A3_LAMBDAS',
  'choice_tag':chosen['tag'] if chosen else None,'choice_recipe_sha256':chosen['recipe_sha256'] if chosen else None,'choice_action':item['action'] if item else None,'predictions':predictions,
  'reason':'PAST_SUPPORT_AND_PREDICTED_ORIGINAL_COMPONENT_MARGIN' if chosen else 'ABSTAIN_NO_PREDICTED_ADMISSIBLE_ACTION','original_qualification_granted':False,'future_qualification_mask_used':False,'current_B_result_used':False,'legacy77_valid':False,'ridge_envelope_is_calibrated_confidence_bound':False}
def predict_control(bundle,raw,control='IF_STUMP',objective='JF_QUALIFIED',*,source_proof=None):
 return a3_predict_control(bundle['inherited_A3_control_bundle'],raw,control,objective,'MERGED',representation='WRENCH39',source_proof=source_proof)
