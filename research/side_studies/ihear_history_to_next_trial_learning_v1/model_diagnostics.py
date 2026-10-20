"""Frozen model diagnostics using development data only; no retraining or physics."""
from pathlib import Path
import json,hashlib
import numpy as np
from learning_models import phi,select,SELECTED
import history_features as hf
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
def main():
    data=read('models/TRAINING_DATA.json')['rows'];z=np.load(P/'models/history_models.npz');mu=z['history_mean'];sd=z['history_std']
    X=np.array([phi((np.array(r['h'])-mu)/sd,r['a']) for r in data]);w=z['ridge_ensemble'];preds=[];advantages=[]
    for group in ['P00R','P05','P08']:
        h=read('learning/'+group+'_T1_HISTORY.json');context=(np.asarray(h['features'])[SELECTED]-mu)/sd
        v=np.array([phi(context,hf.encode_action(a)) for a in hf.grid()])@w[0,:,0]
        advantages.append(dict(patient=group,full_model_predicted_gain_vs_B=(v[0]-v).tolist(),raw_predicted_ranking=np.argsort(v).tolist()))
        for method in ['BO','VALUE']:
            d=select(P,method,h,True);preds.append(dict(patient=group,method=method,selected_index=d['selected_index'],action=d['action'],
                eligible_indices=[i for i,p in enumerate(d['predictions']) if p['eligible']],predictions=d['predictions']))
    result=dict(status='DATA_LIMITED',training_patients=3,rows=len(X),feature_columns=X.shape[1],design_rank=int(np.linalg.matrix_rank(X)),
        regularized_condition_number=float(np.linalg.cond(X.T@X+np.eye(X.shape[1]))),explicit_history_action_interaction_columns=8,
        full_cost_head_interaction_coefficients=w[0,-8:,0].tolist(),full_cost_head_interaction_l2_norm=float(np.linalg.norm(w[0,-8:,0])),
        model_value_cost_error_floor_N_s=float(z['value_cost_error_floor']),model_value_margin_error_floor=float(z['value_margin_error_floor']),
        GP_observation_noise_N_s=float(z['gp_noise_cost']),GP_prior_cost_scale_N_s=float(z['gp_scale_cost']),
        advantages=advantages,training_context_selections=preds,
        disclaimer='Diagnostics on already used development data only; predictions and rank variation are not physical benefit or generalization evidence',
        model_sha256=hashlib.sha256((P/'models/history_models.npz').read_bytes()).hexdigest(),retrained=False,new_physics_starts=0)
    (P/'models/MODEL_DIAGNOSTICS.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print('FROZEN_MODEL_DIAGNOSTICS',json.dumps({k:result[k] for k in ['design_rank','feature_columns','full_cost_head_interaction_l2_norm','model_value_cost_error_floor_N_s','GP_observation_noise_N_s']}),flush=True)
if __name__=='__main__':main()
