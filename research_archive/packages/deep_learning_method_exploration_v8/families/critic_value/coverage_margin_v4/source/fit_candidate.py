"""A4 SOURCE_ONLY fit；调用会拟合，当前未获fit批准。"""
import time
import numpy as np
from causal_api import to_context_full
from a3_reference_api import design,transform
LAMBDAS=[.1,1.,10.]
SCALE_FLOOR=[.1]*5+[1.]*2+[.1]*4+[.005]*4+[.05]*10+[.005]*8+[1.]*3+[.1]*3
HARD_DEADLINE=1793114740.
def check(deadline):
 if time.time()>=min(deadline,HARD_DEADLINE):raise TimeoutError('A4_LOCAL_OR_ORIGINAL_GLOBAL_DEADLINE')
def fit(rows,menu,profiles,ledger,deadline):
 check(deadline);parents=sorted({r['split_parent_group_evaluation_only'] for r in rows})
 contexts={r['split_parent_group_evaluation_only']:to_context_full(r['context'],profiles) for r in rows};indices_state=list(range(39));X=np.asarray([contexts[p]['features'] for p in parents])[:,indices_state];center=X.mean(0);std=X.std(0);scale=np.maximum(std,SCALE_FLOOR)
 spec={'indices':list(range(39)),'center':center.tolist(),'scale':scale.tolist(),'numeric_constant_positions':np.flatnonzero(std<=1e-12).tolist(),'numeric_zero_std_rule':1e-12,'train_parent_groups':parents,'risk_weights':None,'fit_rows':len(rows)}
 zs={p:transform(spec,c) for p,c in contexts.items()};indices={m['recipe_sha256']:i for i,m in enumerate(menu)}
 A=np.asarray([design(zs[r['split_parent_group_evaluation_only']],indices[r['action_recipe_sha256']],len(menu)) for r in rows])
 labels=[r['labels_evaluation_only'] for r in rows]
 Y=np.asarray([r['signed_normalized_original_45_margin']+[r['JF_N_s'],r['JM_Nm_s'],r['delta_JF_N_s'],r['delta_JM_Nm_s']] for r in labels],float)
 assert Y.shape==(len(rows),49) and A.shape==(len(rows),200) and np.isfinite(Y).all()
 target_center=Y.mean(0);target_std=Y.std(0);target_scale=np.maximum(target_std,[.01]*45+[.02,.01,.02,.01]);norm=(Y-target_center)/target_scale
 # Cost原2-RHS block的memory layout/reduction顺序也保持A3；不增加求解。
 for start in [45,47]:
  cost=Y[:,start:start+2].copy();target_center[start:start+2]=cost.mean(0);target_scale[start:start+2]=np.maximum(cost.std(0),[.02,.01]);norm[:,start:start+2]=(cost-target_center[start:start+2])/target_scale[start:start+2]
 constants=np.flatnonzero(target_std[:45]<=1e-12).tolist();norm[:,constants]=0.
 gram=A.T@A;cross=A.T@norm;weights=[];residuals=[]
 for penalty in LAMBDAS:
  check(deadline);entry={'kind':'original_45_margin_and_4_independent_cost_49RHS_ridge','regularization':penalty,'rows':len(rows),'design_dimension':200,'RHS':49,'margin_constant_outputs':constants,'started':time.time()};ledger.append(entry)
  S=gram+penalty*np.eye(200);W=np.linalg.solve(S,cross);entry['completed']=True;entry['elapsed_s']=time.time()-entry['started']
  residual=S@W-cross;cost_residual=float(np.max(np.abs(residual[:,45:]))/max(1.,float(np.max(np.abs(cross[:,45:])))));all_residual=float(np.max(np.abs(residual))/max(1.,float(np.max(np.abs(cross)))))
  assert np.isfinite(W).all() and all_residual<=1e-9 and cost_residual<=1e-9,'A4_NORMAL_EQUATION_RESIDUAL'
  residuals.append({'lambda':penalty,'all49_relative_max_residual':all_residual,'cost4_relative_max_residual':cost_residual,'old_LOCO_lambda_weights_not_archived':True});weights.append(W)
 spec['cost_heads']={kind:{'lambdas':LAMBDAS,'target_center':target_center[start:start+2].tolist(),'target_scale':target_scale[start:start+2].tolist(),'weights':[w[:,start:start+2].tolist() for w in weights]} for kind,start in [('ABS',45),('DELTA_B',47)]}
 spec['margin_head']={'lambdas':LAMBDAS,'target_center':target_center[:45].tolist(),'target_scale':target_scale[:45].tolist(),'raw_train_target_std':target_std[:45].tolist(),'constant_target_positions':constants,'constant_target_rule':'std<=1e-12 => zero normalized target/coefficients and fixed train mean output','weights':[w[:,:45].tolist() for w in weights]}
 spec['support_train_z']=[[zs[r['split_parent_group_evaluation_only']] for r in rows if indices[r['action_recipe_sha256']]==i] for i in range(5)]
 spec['normal_equation_residuals']=residuals;spec['cost_target_normalization_source_rule']='same A3 train-row center/std, floors .02JF/.01JM; 3lambda arithmetic mean'
 return spec
