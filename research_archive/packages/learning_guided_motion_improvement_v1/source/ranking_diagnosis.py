"""Post-lock model-vs-search diagnosis using frozen C models; zero new actions."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
from optimizers import ResidualGP,bounded_pool
from nominal_proxy import NominalProxy

def main():
 analysis=json.loads((P/'OPTIMIZATION_ANALYSIS.json').read_text());result=json.loads((P/'THREE_ARM_RESULTS.json').read_text());base=result['baseline'];rr=result['rows']['C'];last=rr[-1];path=P/last['prediction']['learned_model_path'];record=json.loads(path.read_text());gp=ResidualGP(record['x'],record['residual_targets']);assert max(np.max(abs(a-np.asarray(b))) for a,b in zip(gp.alpha,record['alpha']))<1e-8,'FROZEN_GP_RECONSTRUCTION'
 proxy=NominalProxy();zero=proxy.predict([0,0]);pool=bounded_pool();rows={}
 for arm,selected in analysis['best_all_assigned'].items():
  if selected is None:continue
  x=np.asarray(selected['x']);nom=proxy.predict(x);anchor=np.array([base['JF']+nom['nominal_JF']-zero['nominal_JF'],base['JM']+nom['nominal_JM']-zero['nominal_JM'],base['worst_ratio']]);mu,sd=gp.predict([x]);pred=anchor+mu[0];distance=float(np.min(np.linalg.norm(pool-x,axis=1)));seen=np.asarray(record['x']);rows[arm]={'id':selected['id'],'x':x.tolist(),'actual_JF':selected['JF'],'actual_JM':selected['JM'],'actual_qualified':selected['qualified'],'nominal_anchored_JF':anchor[0],'frozen_last_C_prediction':pred.tolist(),'frozen_C_std':sd[0].tolist(),'frozen_C_predicted_motion_UCB':float(pred[2]+2*sd[0,2]),'min_distance_to_B_C_candidate_pool':distance,'exactly_in_B_C_candidate_pool':distance<1e-12,'distance_to_frozen_C_training_x':float(np.min(np.linalg.norm(seen-x,axis=1))),'actual_information_never_fed_to_any_new_proposal':True}
 counterexamples=[]
 for arm,attempts in result['rows'].items():
  for row in attempts:
   if row.get('complete') and not row.get('qualified'):
    x=np.asarray(row['x']);nom=proxy.predict(x);anchor=np.array([base['JF']+nom['nominal_JF']-zero['nominal_JF'],base['JM']+nom['nominal_JM']-zero['nominal_JM'],base['worst_ratio']]);mu,sd=gp.predict([x]);pred=anchor+mu[0]
    counterexamples.append({'id':row['id'],'arm':arm,'x':row['x'],'actual_JF':row['JF'],'actual_worst_ratio':row['worst_ratio'],'original_failed_requirements':row['motion_vs_B']['failed_requirements'],'frozen_C_predicted_worst_ratio':float(pred[2]),'frozen_C_motion_UCB':float(pred[2]+2*sd[0,2]),'frozen_C_would_predict_motion_pass':bool(pred[2]+2*sd[0,2]<=1),'was_actually_selected_by_C':arm=='C','was_in_frozen_C_training_ids':row['id'] in record['training_attempt_ids'],'same_action_in_frozen_C_training':bool(np.min(np.linalg.norm(np.asarray(record['x'])-x,axis=1))<1e-12),'original_preexecution_C_motion_pass':row['prediction'].get('predicted_original_motion_pass'),'original_preexecution_C_prediction':row['prediction'].get('learned_prediction'),'original_preexecution_C_std':row['prediction'].get('learned_std'),'interpretation':'post-lock query only; action-identical rows across arms form one group. If same_action_in_frozen_C_training is true, this final-model query is in-sample replay, not unseen generalization. Original C preexecution forecast remains the valid error evidence.'})
 interpretation=[]
 if all(a in rows for a in ['A','C']) and rows['A']['actual_JF']<rows['C']['actual_JF']-1e-7:
  if rows['A']['frozen_last_C_prediction'][0]<rows['C']['frozen_last_C_prediction'][0] and rows['A']['frozen_C_predicted_motion_UCB']<=1:
   interpretation.append('Frozen C model ranks A-selected point lower force and predicts margin pass; finite acquisition pool/search/trust/novelty is a supported limitation, not a unique causal identification.')
  else:interpretation.append('Frozen C model fails to rank the actual A-selected improvement or predicts it uncertain/infeasible; surrogate ordering/margin uncertainty remains a plausible limitation.')
 else:interpretation.append('No strict A-over-C force advantage requiring that diagnosis; compare complete fixed-budget and uncertainty records without declaring a unique cause.')
 d={'scope':'POSTHOC_OFFLINE_DIAGNOSIS_ONLY_NO_PHYSICS_NO_NEW_CANDIDATES','frozen_model_path':str(path.relative_to(P)),'frozen_model_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'C_training_ids':record['training_attempt_ids'],'candidate_pool_count':len(pool),'candidate_pool_method':'81 deterministic grid points plus2048 continuous uniform samples; finite approximation over common continuous [-1,1]^2 permissions','rows':rows,'unqualified_complete_counterexamples':counterexamples,'interpretation':interpretation,'new_native_steps':0,'no_retraining_against_A_or_frozen_new_prefix':True,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (P/'audit/POSTHOC_MODEL_VS_SEARCH_DIAGNOSIS.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'rows':rows,'interpretation':interpretation}),flush=True)
if __name__=='__main__':main()
