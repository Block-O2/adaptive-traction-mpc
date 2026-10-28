"""A decision-rule iteration, not retraining or an independent frozen test."""
from pathlib import Path
import json,sys,time
import numpy as np
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
from acl2_shared import read,put,sha
from v7_local_surrogate_v3 import CENTER,SCALE,BOUNDS,kernel,phi
m=read('models/LOCAL_RESPONSE_2D_V1/MODEL.json');Y=np.array([r['targets'] for r in m['training_rows']]);physical=np.array([r['parameters'] for r in m['training_rows']]);X=(physical-CENTER)/SCALE
axes=[np.unique(np.r_[np.linspace(lo,hi,17),physical[:,j],CENTER[j]]) for j,(lo,hi) in enumerate(BOUNDS)]
points=np.array(np.meshgrid(*axes,indexing='ij')).reshape(2,-1).T;Z=(points-CENTER)/SCALE
gps=np.column_stack([kernel(Z,X,h['lengthscale'])@np.array(h['alpha'])*h['output_scale'] for h in m['GP_heads']]);q=phi(Z)@np.array(m['quadratic_coefficients'])
qloo=[]
for i in range(len(X)):
 keep=np.arange(len(X))!=i;c=np.linalg.lstsq(phi(X[keep]),Y[keep],rcond=1e-10)[0];qloo.append((phi(X[i:i+1])@c-Y[i:i+1])[0])
buffer=np.maximum(np.max(abs(np.array([h['LOO_residual'] for h in m['GP_heads']]).T),axis=0),np.max(abs(np.asarray(qloo)),axis=0))
limit=np.array([np.inf,0.,.001,.001,.004]);decisions={}
known={int(np.argmin(np.linalg.norm(points-x,axis=1))):i for i,x in enumerate(physical)}
for name,pred in [('GP_RELATIVE',gps),('QUADRATIC',q)]:
 acq=pred+buffer;eligible=np.all(acq[:,1:]<=limit[1:]+1e-12,axis=1)
 for k,i in known.items():
  acq[k]=Y[i];eligible[k]=m['training_rows'][i]['original_qualified'] and bool(np.all(Y[i,1:]<=limit[1:]+1e-12))
 ix=np.flatnonzero(eligible);chosen=int(ix[np.argmin(acq[ix,0])]);decisions[name]={'parameters':points[chosen].tolist(),'known_id':m['training_rows'][known[chosen]]['id'] if chosen in known else None,'mean_prediction':pred[chosen].tolist(),'acquisition_with_past_actual_labels':acq[chosen].tolist(),'status':'KNOWN_REFERENCE_RETAINED' if chosen in known else 'UNEXECUTED_NEW_PROPOSAL'}
base=read('analysis/native_metrics/DEVPC02_V6PHASE.json');actual=read('analysis/native_metrics/DEVPC02_SHARED_GP_QUAD.json')
target=np.r_[actual['JF']-base['JF'],actual['JM']-base['JM'],np.array(actual['native_motion']['jerk_deg_s3']['rms'])/base['native_motion']['jerk_deg_s3']['rms']-1.,actual['native_force']['norm_rate']['rms']/base['native_force']['norm_rate']['rms']-1.]
errors={k:{'prediction':v['predicted_targets'],'actual_targets':target.tolist(),'actual_minus_prediction':(target-np.array(v['predicted_targets'])).tolist(),'actual_JM_nonincrease':bool(target[1]<=0)} for k,v in m['proposals'].items()}
out={'status':'COMPLETED_OFFLINE_DECISION_ITERATION','created_unix':time.time(),'source_sha256':sha(Path(__file__)),'model_sha256':sha(P/'models/LOCAL_RESPONSE_2D_V1/MODEL.json'),'training_data_unchanged':True,'new_training':0,'new_physical':0,'same_common_development_errorbuffer':buffer.tolist(),'buffer_scope':'Heuristic max same-development actionLOO residual, no uncertaintycalibration or safetyguarantee. Selection uses only original9 trainingresponses; prospective outcome retained separately forerrorreport.','decision_revision':decisions,'original_prospective_prediction_errors':errors,'formal_original_negative_outcome_unchanged':True,'failure_mechanism_confirmed':'Meanpredicted JM margin was far smaller than developmenterror; actual JM sign wrong','failure_mechanism_not_confirmed':'Exact nonlinear/clearance/rolling branch cause not causallyidentified; tinyresponse could be inadequatelyrepresented by sampled interpolation','next_decision':'No independentGP benefit: samepointas simpler quadratic, actual dualcosttarget failed, conservativerule retains knownreference. Stop narrow2DGP unless newcase actual actionranking creates meaningful decisiongap.'}
put('analysis/LOCAL_RESPONSE_MARGIN_AUDIT_V2.json',out);print('MARGIN_AUDIT',decisions,'actual',target.tolist(),'buffer',buffer.tolist())
