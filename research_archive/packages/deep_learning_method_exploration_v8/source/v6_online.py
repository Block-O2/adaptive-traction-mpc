"""Prediction logging at H, before future outcomes exist; no plant/scorer access."""
import numpy as np,time,hashlib,json
from v6_model import predict_cost
from v6_observed_risk import predict as predict_risk
from v6_observed_history import boundary as observed_history_boundary
from v6_eligibility import predict as predict_eligibility

def predict_at_h(study,b,feature,config,put):
 preparation_started=time.perf_counter()
 if not config.get('frozen_bundle') or abs(feature['horizon_s']-.5)>1e-9 or (study.active_policy_tag=='B' and not config.get('B_is_candidate')):return
 assert not (study.package_path/'runtime/source/results'/(study.child['label']+'_'+study.child['kind'])/'summary.json').exists(),'FUTURE_OUTCOME_ALREADY_EXISTS_AT_H'
 path=study.package_path/config['frozen_bundle'];raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==config['frozen_bundle_sha256'],'FROZEN_MODEL_CHANGED'
 bundle=json.loads(raw)['phases'][config['fork_phase']];history_features=observed_history_boundary(b);feature=dict(feature);feature['feature_names']=feature['feature_names']+['causal_upstream_COMPOSE_0'];feature['features']=feature['features']+[float(config.get('upstream_policy')=='COMPOSE' and study.active_policy_tag!='B')];at=float(b['physical_now']);now=dict(time_s=at,estimated_q_dq=b['observation'].as_array(),measured_force=b['interface'].measured_force_world_n)
 h=[r for r in study.causal if r['time_s']<=at+1e-9]+[now];t=np.array([r['time_s'] for r in h]);x=np.array([r['estimated_q_dq'] for r in h]);f=np.array([r['measured_force'] for r in h]);keep=np.r_[True,np.diff(t)>1e-10];t,x,f=t[keep],x[keep],f[keep]
 dt=np.diff(t);a=np.diff(x[:,2:],axis=0)/dt[:,None];j=np.diff(a,axis=0)/dt[1:,None];local=np.r_[np.max(abs(x[:,2:]),0),np.max(abs(a),0),np.max(abs(j),0),np.ptp(x[:,:2],0)].tolist();inputs=dict(feature_names=feature['feature_names'],features=feature['features'],local_risk_features=local,history_risk_features=history_features)
 start=time.perf_counter();cost=predict_cost(bundle['cost'],inputs);risk=predict_risk(bundle['risk'],inputs);eligibility_risk=predict_eligibility(bundle.get('eligibility',{}),inputs);elapsed=time.perf_counter()-start;short=float(np.linalg.norm(f[:-1],axis=1)@dt)
 put('predictions/'+study.child['label']+'_'+study.child['kind']+'_H05.json',dict(tag=study.active_policy_tag,created_unix=time.time(),physical_s=at,cost=cost,risk=risk,eligibility_risk=eligibility_risk,short_JF=short,score=short+cost['mean'][bundle['score_index']],inference_wall_s=elapsed,prediction_preparation_wall_s=time.perf_counter()-preparation_started,import_overhead_included=False,full_task_outcome_exists=False,uses_native_truth=False,frozen_bundle_sha256=config['frozen_bundle_sha256'],local_risk_features=local,history_risk_features=history_features))
