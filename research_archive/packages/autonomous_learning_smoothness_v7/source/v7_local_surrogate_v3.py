"""Local same-state action-response capability. Separate physical targets; no weighted reward."""
from pathlib import Path
import os,sys,json,time,copy,hashlib,resource
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'))
import numpy as np
from acl2_shared import put,sha,read

CENTER=np.array([-.9571745795248379,-.9859247321976443]);SCALE=np.array([.02,.025])
BOUNDS=np.array([[CENTER[0]-.02,CENTER[0]+.02],[-1.,-.95]])
TARGETS=['delta_JF_N_s','delta_JM_Nm_s','hip_jerk_RMS_ratio_minus1','knee_jerk_RMS_ratio_minus1','force_norm_rate_RMS_ratio_minus1'];FLOOR=np.array([.1,.1,.0005,.0005,.001])

def policy_signature(action):
 a=copy.deepcopy(action)
 for i in [3,7]:a['x'][i]=0.
 return json.dumps(a,sort_keys=True)
def collect(group):
 assert read('owned/'+group+'_SUPERVISOR_END.json')['worker_exit_code']==0,'COUPLED_JOB_NOT_COMPLETED'
 proofpath=P/'audit'/(group+'_LOCAL_FULL_PARENT_EQUIVALENCE.json');proof=json.loads(proofpath.read_text())
 assert proof['status']=='PASS' and proof['groups']==[group],'FULL_CAUSAL_PARENT_PROOF_REQUIRED'
 for rel,expected in proof['bound_files_sha256'].items():assert sha(P/rel)==expected,'PARENT_PROOF_INPUT_CHANGED:'+rel
 baseid=group+'_V6PHASE';base=read('analysis/native_metrics/'+baseid+'.json');baseact=read('attempts/'+baseid+'_RESULT.json')['action'];sig=policy_signature(baseact);rows=[];seen={};parent=set()
 ids=[group+'_'+t for t in ['V6PHASE','REL_M','REL_P','SPD_M','SPD_P','MM','MP','PM','PP']]
 for id in ids:
  rf=P/'attempts'/(id+'_RESULT.json');r=json.loads(rf.read_text());assert r['complete'],'PARTIAL_NOT_A_TRAINING_SUCCESS';a=r['action'];assert policy_signature(a)==sig,'POLICY_AUTHORITY_OR_NONLOCAL_CHANGE'
  mf=P/'analysis/native_metrics'/(id+'.json');m=json.loads(mf.read_text());snap=read('runtime/reports/'+id+'_SNAPSHOT.json');parent.add(snap['manifest']['native_integration']['sha256'])
  x=np.array(a['x'])[[3,7]];key=tuple(np.round(x,12));y=np.r_[m['JF']-base['JF'],m['JM']-base['JM'],np.array(m['native_motion']['jerk_deg_s3']['rms'])/base['native_motion']['jerk_deg_s3']['rms']-1.,m['native_force']['norm_rate']['rms']/base['native_force']['norm_rate']['rms']-1.]
  if key in seen:
   assert np.max(abs(y-seen[key]['targets']))<1e-8,'DUPLICATE_ACTION_RESPONSE_MISMATCH';continue
  row={'id':id,'parameters':x.tolist(),'targets':y.tolist(),'original_qualified':m['qualified_original'],'metrics_sha256':sha(mf),'result_sha256':sha(rf),'raw_hashes':m['source_hashes'],'native_integration_sha256':next(iter(parent))};rows.append(row);seen[key]=row
 assert len(parent)==1,'MIXED_PHYSICAL_PARENTS'
 assert len(rows)==9,'EXPECTED_NINE_DISTINCT_SAME_FORK_RESPONSES'
 return rows,base,baseact,{'path':str(proofpath.relative_to(P)),'sha256':sha(proofpath)}

def kernel(x,z,length):return np.exp(-.5*np.sum((x[:,None,:]-z[None,:,:])**2,axis=2)/length**2)
def gp_fit(x,y,length):
 K=kernel(x,x,length)+np.eye(len(x))*1e-7;inverse=np.linalg.solve(K,np.eye(len(x)));alpha=inverse@y;return inverse,alpha

def phi(x):
 # Full 2D quadratic on the measured two-parameter plane.
 return np.column_stack([np.ones(len(x)),x,x*x,x[:,0]*x[:,1]])

def run(group,model_name):
 start=time.time();cpu0=resource.getrusage(resource.RUSAGE_SELF);out='models/'+model_name;assert not (P/out).exists(),'UNIQUE_MODEL_ID_REQUIRED'
 rows,base,baseact,parent_proof=collect(group);physical=np.array([r['parameters'] for r in rows]);X=(physical-CENTER)/SCALE;Y=np.array([r['targets'] for r in rows]);yscale=np.maximum(np.std(Y,axis=0),FLOOR);heads=[];fitcalls=0
 for j,name in enumerate(TARGETS):
  alternatives=[]
  for length in [.5,1.,2.]:
   # Exact GP LOO identity, not an independent state or patient test.
   inv,alpha=gp_fit(X,Y[:,j]/yscale[j],length);fitcalls+=1;loo=(alpha/np.diag(inv))*yscale[j];alternatives.append((float(np.sqrt(np.mean(loo*loo))),length,inv,alpha,loo))
  rmse,length,inv,alpha,loo=min(alternatives,key=lambda q:q[0]);heads.append({'target':name,'lengthscale':length,'output_scale':yscale[j],'inverse':inv.tolist(),'alpha':alpha.tolist(),'action_LOO_RMSE':rmse,'LOO_residual':loo.tolist(),'alternatives':[{'lengthscale':a[1],'LOO_RMSE':a[0]} for a in alternatives]})
 coefficients=np.linalg.lstsq(phi(X),Y,rcond=1e-10)[0];ql=[]
 for i in range(len(X)):
  keep=np.arange(len(X))!=i;c=np.linalg.lstsq(phi(X[keep]),Y[keep],rcond=1e-10)[0];ql.append(phi(X[i:i+1])@c-Y[i:i+1])
 qloo=np.concatenate(ql);quadratic_rmse=np.sqrt(np.mean(qloo*qloo,axis=0))
 axes=[np.unique(np.r_[np.linspace(lo,hi,17),physical[:,j],CENTER[j]]) for j,(lo,hi) in enumerate(BOUNDS)]
 candidate_physical=np.array(np.meshgrid(*axes,indexing='ij')).reshape(2,-1).T;Z=(candidate_physical-CENTER)/SCALE;pred=[];std=[]
 for h in heads:
  k=kernel(Z,X,h['lengthscale']);inv=np.array(h['inverse']);pred.append(k@np.array(h['alpha'])*h['output_scale']);std.append(np.sqrt(np.maximum(0.,1.-np.einsum('ij,ij->i',k@inv,k)))*h['output_scale'])
 gp=np.column_stack(pred);uncert=np.column_stack(std);quad=phi(Z)@coefficients
 threshold=np.array([np.inf,0.,.001,.001,.004]);proposals={}
 admissible=[i for i,r in enumerate(rows) if r['original_qualified'] and np.all(Y[i,1:]<=threshold[1:]+1e-12)]
 assert admissible,'NO_OBSERVED_QUALIFIED_REFERENCE'
 incumbent=min(admissible,key=lambda i:Y[i,0]);incumbent_grid=None;known_grid={}
 for i,r in enumerate(rows):
  idx=int(np.argmin(np.linalg.norm(candidate_physical-physical[i],axis=1)))
  assert np.max(abs(candidate_physical[idx]-physical[i]))<1e-10,'OBSERVED_POINT_MISSING_FROM_GRID'
  known_grid[idx]=i
  if i==incumbent:incumbent_grid=idx
 assert incumbent_grid is not None
 for method,predictions in [('GP_RELATIVE',gp),('QUADRATIC',quad)]:
  # Past exact outcomes are available data. Preserve every known feasible point
  # with its measured objective, and exclude known failures. No future labels.
  acquisition=predictions.copy();feasible=np.all(predictions[:,1:]<=threshold[1:]+1e-12,axis=1)
  for idx,i in known_grid.items():
   acquisition[idx]=Y[i];feasible[idx]=i in admissible
  assert feasible[incumbent_grid],'OBSERVED_INCUMBENT_MASKED'
  options=np.flatnonzero(feasible);idx=int(options[np.argmin(acquisition[options,0])]);point=candidate_physical[idx];fallback=idx==incumbent_grid
  duplicate=next((r['id'] for r in rows if np.max(abs(np.array(r['parameters'])-point))<1e-10),None);action=copy.deepcopy(baseact)
  for dim,value in zip([3,7],point):action['x'][dim]=float(value)
  off_support=False
  proposals[method]={'parameters':point.tolist(),'action':action,'predicted_targets':predictions[idx].tolist(),'acquisition_targets_known_replaced_by_actual':acquisition[idx].tolist(),'GP_uncertainty_if_applicable':uncert[idx].tolist() if method=='GP_RELATIVE' else None,'mean_feasibility_only':not bool(duplicate),'uncertainty_not_calibrated':True,'duplicate_observed_id':duplicate,'fallback_to_observed':fallback,'status':'SELECTS_KNOWN_TRADITIONAL_POINT' if duplicate else 'UNTRIED_ACTION_PROPOSAL','qualified_original':rows[known_grid[idx]]['original_qualified'] if idx in known_grid else None,'predicted_JF_gain_over_reference':float(-acquisition[idx,0]),'predicted_JF_gain_over_strongest_observed_incumbent':float(Y[incumbent,0]-acquisition[idx,0]),'off_measured_subspace':off_support,'physical_trial_authorization':'NOT_STARTED; main must register/freeze proposal test with original gates'}
 model={'schema':'ihear.local_relative_response.v3.2d_same_fork','model_id':model_name,'source_sha256':sha(Path(__file__)),'created_unix':time.time(),'group':group,'input_names':['RETURN_relative_path_x3','RETURN_pass_speed_x7'],'center':CENTER.tolist(),'input_scales':SCALE.tolist(),'domain_bounds':BOUNDS.tolist(),'targets':TARGETS,'training_rows':rows,'causal_parent_equivalence_proof':parent_proof,'target_reference_id':base['id'],'strongest_observed_feasible_incumbent':{'id':rows[incumbent]['id'],'parameters':physical[incumbent].tolist(),'actual_targets':Y[incumbent].tolist()},'GP_heads':heads,'quadratic_coefficients':coefficients.tolist(),'quadratic_basis':'[1,normalizedx3,x7,x3^2,x7^2,x3*x7]','quadratic_design_rank':int(np.linalg.matrix_rank(phi(X))),'quadratic_design_condition':float(np.linalg.cond(phi(X))),'quadratic_action_LOO_RMSE':quadratic_rmse.tolist(),'LOO_model_selection_bias':'lengthscale chosen with same actionLOO; tuning diagnostic only, not unbiased validation','RETURN_time_x5_frozen':.9668651272926947,'training_GP_queries':fitcalls,'candidate_grid_size':len(Z),'proposals':proposals,'physical_target_aggregation':'None: minimize predicted deltaJF subject to separate predictedJM/jerk/force-rate constraints; original task/motion qualification still final','scope':'All labels one exposed actual parent; action LOO is interpolation diagnostic, not independent-state or patient validation','hidden_physical_features_used':False,'future_execution_features_used':False,'native_motion_used_for_labels_only':True,'new_physics':0,'new_PPO_episodes':0,'new_Adam_updates':0}
 put(out+'/MODEL.json',model);cpu=resource.getrusage(resource.RUSAGE_SELF);put(out+'/TRAINING_ACCOUNTING.json',{'model_id':model_name,'status':'TRAINED_AND_PROPOSED','training_unique_actions':len(rows),'training_unique_physical_parents':1,'used_training_ids':[r['id'] for r in rows],'historical_label_cost_not_free':True,'wall_seconds':time.time()-start,'CPU_user_seconds':cpu.ru_utime-cpu0.ru_utime,'CPU_system_seconds':cpu.ru_stime-cpu0.ru_stime,'kernel_solves':fitcalls,'least_squares_fits':len(X)+1,'candidate_GP_rows_per_head':len(Z),'candidate_head_queries_total':len(Z)*len(heads),'gradient_updates':0,'Adam_updates':0,'PPO_episodes':0,'new_physics':0,'source_sha256':sha(Path(__file__))})
 put(out+'/SOURCE_DATA_MANIFEST.json',{'source_sha256':sha(Path(__file__)),'model_sha256':sha(P/out/'MODEL.json'),'training_metrics':{r['id']:r['metrics_sha256'] for r in rows},'training_results':{r['id']:r['result_sha256'] for r in rows},'raw':{r['id']:r['raw_hashes'] for r in rows}})
 print('LOCAL_SURROGATE_TRAINED',model_name,'uniqueactions',len(rows),'GP_LOO',[h['action_LOO_RMSE'] for h in heads],'QUAD_LOO',quadratic_rmse.tolist(),'proposals',{k:{z:v[z] for z in ['parameters','status','predicted_targets']} for k,v in proposals.items()},flush=True)
 return model
if __name__=='__main__':run(sys.argv[1],sys.argv[2])
