"""SOURCE_ONLY F1 common-OUT0 fixed ridge diagnostics; no fit on import.

Requires separate root approval bound to actual INDEX/NPZ/manifest bytes.
F2 neural training is deliberately unavailable in this entrypoint.
"""
from pathlib import Path
import argparse,hashlib,json,math,os,platform,resource,signal,sys,time,traceback

HERE=Path(__file__).resolve().parent;PACKAGE=HERE.parents[2]
STOP=1793114740.;ACTIVATION='deep_learning_method_exploration_v8_20261027T032540Z'
REL='families/learning_assisted/common_out0_v2/'
DATA_REL=REL+'data/build_v1/';OUT_REL=REL+'fits/f1_v1'
SOURCE_REL=REL+'FIT_F1_SOURCE_MANIFEST_V1.json';CONTRACT_REL=REL+'FIT_F1_FROZEN_CONTRACT_V1.json'
DIRECT=('ACTION_BLIND39_ABSOLUTE','ACTION_ONLY_GLOBAL_RECIPE','CONTEXT_ACTION_ABSOLUTE','CONTEXT_ACTION_KINEMATIC_RESIDUAL','PAIRED_CONTEXT_ACTION_DELTA_VS_B')
CURVE=('ACTION_BLIND_ANCHORED_CURVE','CONTEXT_ACTION_ANCHORED_CURVE','CONTEXT_ACTION_KINEMATIC_RESIDUAL_CURVE')
NPZ_KEYS={'endpoint14','window_JF_JM','dense14','dense_cost_JF_JM','dense_actual_elapsed_s','dense_public_query_s','horizons_s'}

def need(test,reason):
    if not test:raise ValueError(reason)
def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def write_new(p,o):
    with Path(p).open('x') as f:json.dump(o,f,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def append(p,o):
    with Path(p).open('a') as f:f.write(json.dumps(o,sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

class Work:
    def __init__(self,out,deadline):
        self.out=out;self.deadline=deadline;self.c=dict(normalizer_fits=0,matrix_solve_attempts=0,matrix_solve_successes=0,scalar_head_solutions_attempted=0,linear_design_training_rows=0,prediction_API_calls=0,prediction_query_vectors=0,fixed_baseline_query_vectors=0,parameter_gradient_updates=0,physics=0)
    def guard(self):need(time.monotonic()<self.deadline and time.time()<STOP,'ORIGINAL_F1_LOCAL_OR_GLOBAL_DEADLINE')
    def event(self,kind,**kw):self.guard();append(self.out/'WORK_EVENTS.jsonl',dict(event=kind,unix=time.time(),counters=dict(self.c),**kw))

def initial14(x,np):return x[:,25:39].copy()
def baseline14(x,tau,kinematic,np):
    y=initial14(x,np);t=np.asarray(tau,float)
    if t.ndim==0:t=np.full(len(x),float(t))
    if kinematic:
        for q,dq in [(0,2),(1,3),(4,6),(5,7)]:y[:,q]+=t*y[:,dq]
    return y
def baseline16(x,tau,kinematic,np):
    y=baseline14(x,tau,kinematic,np);return np.c_[y,np.linalg.norm(y[:,8:11],axis=1)*tau,np.linalg.norm(y[:,11:14],axis=1)*tau]
def design(z,action,kind,np):
    if kind.startswith('ACTION_BLIND'):return np.c_[np.ones(len(z)),z]
    one=np.eye(5)[action]
    if kind=='ACTION_ONLY_GLOBAL_RECIPE':return one
    if kind=='PAIRED_CONTEXT_ACTION_DELTA_VS_B':one=one[:,1:]
    return np.c_[one,(one[:,:,None]*z[:,None,:]).reshape(len(z),-1)]
def curve_design(z,action,tau,kind,np):
    d=design(z,action,'ACTION_BLIND39_ABSOLUTE' if kind.startswith('ACTION_BLIND') else 'CONTEXT_ACTION_ABSOLUTE',np)
    return np.c_[d*tau[:,None],d*(tau*tau)[:,None]]

def ridge(D,Y,work,label,center_targets,np):
    work.guard();need(D.ndim==Y.ndim==2 and D.shape[0]==Y.shape[0] and D.shape[1]<=400 and Y.shape[1]<=16,'REGISTERED_MULTIHEAD_DIMENSION_CAP')
    need(np.all(np.isfinite(D)) and np.all(np.isfinite(Y)),'FINITE_TRAINING_DATA')
    center=Y.mean(axis=0) if center_targets else np.zeros(Y.shape[1]);scale=Y.std(axis=0);scale=np.where(scale<1e-9,1.,scale)
    work.c['linear_design_training_rows']+=len(D);work.c['matrix_solve_attempts']+=1;work.c['scalar_head_solutions_attempted']+=Y.shape[1];need(work.c['matrix_solve_attempts']<=253,'NO_EXTRA_FITS_OR_HYPERSEARCH')
    work.event('SOLVE_START',label=label,dimension=D.shape[1],heads=Y.shape[1],training_query_rows=len(D))
    weights=np.linalg.solve(D.T@D+10.*np.eye(D.shape[1]),D.T@((Y-center)/scale))
    need(np.all(np.isfinite(weights)),'NONFINITE_WEIGHTS');work.c['matrix_solve_successes']+=1
    model=dict(weights=weights.tolist(),target_center=center.tolist(),target_scale=scale.tolist(),ridge_alpha=10.)
    work.event('SOLVE_RETURN',label=label,model_sha256=digest(model))
    return model
def linear_predict(D,model,work,np):
    work.guard();work.c['prediction_API_calls']+=1;work.c['prediction_query_vectors']+=len(D)
    need(work.c['prediction_query_vectors']<=1000000,'REGISTERED_F1_PREDICTION_QUERY_CAP')
    answer=D@np.asarray(model['weights'])*np.asarray(model['target_scale'])+np.asarray(model['target_center'])
    need(np.all(np.isfinite(answer)),'NONFINITE_PREDICTION_NO_CLIP');return answer

def score_response(indices,pred,true,rows,paired,work,np):
    """Future labels are used only here for diagnostic scoring, never selection mask."""
    result=[];unit_scale=np.r_[np.full(8,180./math.pi),np.ones(8)]
    cases=sorted({rows[i]['evaluation_only']['case_sha256'] for i in indices})
    for case in cases:
        pos=[j for j,i in enumerate(indices) if rows[i]['evaluation_only']['case_sha256']==case]
        ids=[indices[j] for j in pos];p=pred[pos];y=true[pos];b=next(j for j,i in enumerate(ids) if rows[i]['input']['recipe_index']==0)
        truth_delta=y-y[b];delta=p if paired else p-p[b];nonb=[j for j in range(len(ids)) if j!=b]
        target=truth_delta if paired else y;error=(p-target)*unit_scale
        costs={}
        for c,name,eps in [(14,'JF',1e-6),(15,'JM',1e-7)]:
            actual=truth_delta[nonb,c];forecast=delta[nonb,c];err=np.abs(forecast-actual);mask=np.abs(actual)>eps
            denom=int(mask.sum());forecast_sign=np.where(np.abs(forecast)<=eps,0.,np.sign(forecast));correct=int(np.sum(forecast_sign[mask]==np.sign(actual[mask])))
            zero=float(np.mean(np.abs(actual)))
            costs[name]=dict(paired_MAE=float(err.mean()),zero_effect_MAE=zero,skill_vs_zero=None if zero<=eps else 1.-float(err.mean())/zero,
                true_nontie_count=denom,true_tie_count=len(nonb)-denom,sign_correct_count=correct,sign_accuracy=None if not denom else correct/denom,predicted_tie_count=int(np.sum(np.abs(forecast)<=eps)))
        concordant=discordant=pred_ties=true_ties=0
        for i in range(len(ids)):
            for j in range(i):
                actual=y[i,14]-y[j,14];forecast=p[i,14]-p[j,14]
                if abs(actual)<=1e-6:true_ties+=1;continue
                if abs(forecast)<=1e-6:pred_ties+=1
                elif actual*forecast>0:concordant+=1
                else:discordant+=1
        minimum=float(np.min(p[:,14]));tied=[j for j in range(len(ids)) if p[j,14]<=minimum+1e-6]
        best=min(tied,key=lambda j:rows[ids[j]]['input']['recipe_index'])
        e=rows[ids[best]]['evaluation_only']
        result.append(dict(case_sha256_evaluation_only=case,group_evaluation_only=e['group'],observed_recipes=len(ids),B_attempt_id=rows[ids[b]]['id'],
            channel_MAE_physical_units=np.mean(np.abs(error),axis=0).tolist(),channel_RMSE_physical_units=np.sqrt(np.mean(error*error,axis=0)).tolist(),
            channel_units=['deg','deg','deg/s','deg/s','deg','deg','deg/s','deg/s','N','N','N','Nm','Nm','Nm','Ns','Nms'],
            target_semantics='paired_delta_vs_B' if paired else 'absolute_endpoint14_and_window_cost',cost_effects=costs,
            ranking=dict(concordant=concordant,discordant=discordant,predicted_ties=pred_ties,true_ties=true_ties,pairwise_accuracy=None if concordant+discordant+pred_ties==0 else concordant/(concordant+discordant+pred_ties)),
            hypothetical_window_min_choice=rows[ids[best]]['id'],window_JF_regret=float(y[best,14]-np.min(y[:,14])),
            actual_original_full_qualification_of_choice_evaluation_only=e['original_qualified'],future_qualification_mask_used=False,window_cost_grants_full_task_qualification=False,
            negative_absolute_window_cost_predictions=None if paired else dict(JF=int(np.sum(p[:,14]<0.)),JM=int(np.sum(p[:,15]<0.))),
            paired_JF_prediction_N_s=delta[:,14].tolist(),paired_JM_prediction_Nm_s=delta[:,15].tolist(),paired_actual_JF_N_s=truth_delta[:,14].tolist(),paired_actual_JM_Nm_s=truth_delta[:,15].tolist()))
    return result

def perform(root,out,approval,work,np):
    from common_out0_interface_v1 import FEATURE_NAMES
    contract=load(root/CONTRACT_REL);index=load(root/DATA_REL/'INDEX.json');manifest=load(root/DATA_REL/'DATASET_MANIFEST.json');receipt=load(root/DATA_REL/'BUILD_EXECUTION_RECEIPT.json')
    need(index['schema']=='v8.E.common_out0_prediction_index.v1' and index['feature_names']==FEATURE_NAMES,'ACTUAL_INDEX_SCHEMA')
    need(manifest['status']=='BUILT_ORIGINAL_SOURCE_BOUND_NO_FIT' and receipt['status']=='PASS_ONE_SHOT_DATASET_BUILD_NO_FIT','BUILT_CLOSED_DATA_ONLY')
    need(manifest['actual_rows']==48 and manifest['parent_contexts']==manifest['distinct_case_SHA']==10,'EXACT48_TEN_CASES')
    for name,expected in contract['dataset_files_sha256'].items():need(sha(root/DATA_REL/name)==expected,'ACTUAL_DATASET_BYTES:'+name)
    with np.load(root/DATA_REL/'TARGETS_CAUSAL_ONLY.npz',allow_pickle=False) as f:
        need(set(f.files)==NPZ_KEYS,'EXACT_FUTURE_LABEL_ALLOWLIST');data={k:f[k] for k in NPZ_KEYS}
    rows=index['rows'];need(len(rows)==48 and len({r['id'] for r in rows})==48,'EXACT_PHYSICAL_ROW_IDENTITIES')
    x=np.asarray([r['input']['features'] for r in rows],float);action=np.asarray([r['input']['recipe_index'] for r in rows],int)
    cases=[r['evaluation_only']['case_sha256'] for r in rows];unique=sorted(set(cases));need(len(unique)==10 and x.shape==(48,39) and np.all(np.isfinite(x)),'INPUT39_ONLY')
    need(data['endpoint14'].shape==(48,7,14) and data['window_JF_JM'].shape==(48,7,2) and data['dense14'].shape==(48,3201,14),'ACTUAL_TARGET_SHAPES')
    need(np.array_equal(data['dense14'][:,0],initial14(x,np)),'ORIGINAL_OUT0_INPUT_VS_LABEL_ZERO_NODE')
    need(np.array_equal(data['horizons_s'],np.array([.5,1.,2.,4.,8.,12.,16.])) and np.array_equal(data['dense_public_query_s'],np.arange(3201)*.005),'PUBLIC_QUERY_CLOCK')
    target=np.concatenate([data['endpoint14'],data['window_JF_JM']],axis=2)
    paired=target.copy()
    for case in unique:
        ids=[i for i,c in enumerate(cases) if c==case];b=next(i for i in ids if action[i]==0)
        need(all(np.array_equal(x[i],x[b]) for i in ids),'SAME_PARENT_INPUT39_PER_CASE')
        paired[ids]-=target[b]
    results=[];curve_results=[];all_models={};curve_models={};normalizers={}
    for fold in [None]+unique:
        work.guard();label='ALL_DEVELOPMENT' if fold is None else 'LEAVE_CASE_'+fold
        train=[i for i,c in enumerate(cases) if c!=fold];test=list(range(48)) if fold is None else [i for i,c in enumerate(cases) if c==fold]
        representatives=[next(i for i in train if cases[i]==c) for c in unique if c!=fold]
        work.c['normalizer_fits']+=1;center=x[representatives].mean(axis=0);scale=x[representatives].std(axis=0);scale=np.where(scale<1e-9,1.,scale);z=(x-center)/scale
        normalizer=dict(center=center.tolist(),scale=scale.tolist(),training_distinct_contexts=len(representatives),training_only=True)
        normalizers[label]=normalizer
        for h in range(4):
            horizon=float(data['horizons_s'][h]);true=target[test,h]
            for kind in DIRECT:
                ispair=kind.startswith('PAIRED');Y=paired[:,h] if ispair else target[:,h]
                base=baseline16(x,horizon,True,np) if kind=='CONTEXT_ACTION_KINEMATIC_RESIDUAL' else np.zeros_like(Y)
                D=design(z,action,kind,np);model=ridge(D[train],(Y-base)[train],work,label+'/'+kind+'/'+str(horizon),not ispair,np)
                pred=linear_predict(D[test],model,work,np)+base[test]
                reports=score_response(test,pred,true,rows,ispair,work,np)
                results.extend(dict(fold=label,method=kind,horizon_s=horizon,**r) for r in reports)
                append(out/'MODEL_SNAPSHOTS.jsonl',dict(fold=label,method=kind,horizon_s=horizon,normalizer=normalizer,model=model,actual_training_rows=len(train),target_semantics='PAIR_DELTA' if ispair else 'ABSOLUTE'))
                if fold is None:all_models[kind+'/'+str(horizon)]=dict(model=model,normalizer=normalizer,baseline='KINEMATIC' if kind=='CONTEXT_ACTION_KINEMATIC_RESIDUAL' else None,paired_delta=ispair)
            for name,kinematic in [('PERSISTENCE',False),('KINEMATIC',True)]:
                work.c['fixed_baseline_query_vectors']+=len(test);pred=baseline16(x[test],horizon,kinematic,np)
                results.extend(dict(fold=label,method=name,horizon_s=horizon,**r) for r in score_response(test,pred,true,rows,False,work,np))
        # Dense training queries never exceed4s. No observed future state enters D.
        sample_nodes=np.arange(0,801,4);tau_train=np.tile(sample_nodes*.005,len(train));x_train=np.repeat(x[train],len(sample_nodes),axis=0)
        z_train=np.repeat(z[train],len(sample_nodes),axis=0);a_train=np.repeat(action[train],len(sample_nodes));Y=data['dense14'][train][:,sample_nodes].reshape(-1,14)
        for kind in CURVE:
            kinematic=kind=='CONTEXT_ACTION_KINEMATIC_RESIDUAL_CURVE';base=baseline14(x_train,tau_train,kinematic,np)
            D=curve_design(z_train,a_train,tau_train,kind,np);model=ridge(D,Y-base,work,label+'/'+kind,False,np)
            append(out/'MODEL_SNAPSHOTS.jsonl',dict(fold=label,method=kind,normalizer=normalizer,model=model,training_times_max_s=4.,target_anchor='KINEMATIC' if kinematic else 'INITIAL14'))
            if fold is None:curve_models[kind]=dict(model=model,normalizer=normalizer,baseline='KINEMATIC' if kinematic else 'INITIAL14')
            forecasts=[];state_errors=[]
            for i in test:
                t=data['dense_public_query_s'];xx=np.repeat(x[i:i+1],len(t),axis=0);zz=np.repeat(z[i:i+1],len(t),axis=0);aa=np.full(len(t),action[i],int)
                pred=linear_predict(curve_design(zz,aa,t,kind,np),model,work,np)+baseline14(xx,t,kinematic,np)
                need(np.array_equal(pred[0],data['dense14'][i,0]),'EXACT_INITIAL_ANCHOR')
                v=np.c_[np.linalg.norm(pred[:-1,8:11],axis=1),np.linalg.norm(pred[:-1,11:14],axis=1)]*.005;cum=np.vstack([np.zeros((1,2)),np.cumsum(v,axis=0)])
                ix=(data['horizons_s']/.005).round().astype(int);forecasts.append(np.c_[pred[ix],cum[ix]])
                err=pred-data['dense14'][i];unit=np.r_[np.full(8,180./math.pi),np.ones(6)]
                errors=[]
                for h,k in zip(data['horizons_s'],ix):
                    errors.append(dict(horizon_s=float(h),channel_MAE=np.abs(err[:k+1]*unit).mean(axis=0).tolist(),endpoint_abs_error=np.abs(err[k]*unit).tolist(),predicted_window_JF_JM=cum[k].tolist(),actual_window_JF_JM=data['window_JF_JM'][i,list(ix).index(k)].tolist()))
                state_errors.append(dict(id=rows[i]['id'],errors=errors,future_state_reference_wrench_feedback=False))
            forecasts=np.asarray(forecasts)
            for h,horizon in enumerate(data['horizons_s']):curve_results.extend(dict(fold=label,method=kind,horizon_s=float(horizon),training_times_max_s=4.,**r) for r in score_response(test,forecasts[:,h],target[test,h],rows,False,work,np))
            append(out/'CURVE_ERRORS.jsonl',dict(fold=label,method=kind,prediction_kind='fixed_OUT0_query_curve_not_Markov_simulator',rows=state_errors))
        work.event('FOLD_COMPLETE',fold=label)
    need(work.c['matrix_solve_attempts']==work.c['matrix_solve_successes']==253 and work.c['normalizer_fits']==11,'EXACT_PREREGISTERED_F1_FIT_COUNTS')
    # Explicit direct-cost versus integrated-wrench disagreement; no score mixing.
    curve_map={(r['fold'],r['case_sha256_evaluation_only'],r['horizon_s']):r for r in curve_results if r['method']=='CONTEXT_ACTION_KINEMATIC_RESIDUAL_CURVE'}
    consistency=[]
    for r in results:
        if r['method']!='CONTEXT_ACTION_KINEMATIC_RESIDUAL':continue
        curve=curve_map[(r['fold'],r['case_sha256_evaluation_only'],r['horizon_s'])]
        consistency.append(dict(fold=r['fold'],case_sha256_evaluation_only=r['case_sha256_evaluation_only'],horizon_s=r['horizon_s'],deltaJF_direct_minus_integrated_curve=(np.asarray(r['paired_JF_prediction_N_s'])-np.asarray(curve['paired_JF_prediction_N_s'])).tolist(),deltaJM_direct_minus_integrated_curve=(np.asarray(r['paired_JM_prediction_Nm_s'])-np.asarray(curve['paired_JM_prediction_Nm_s'])).tolist()))
    write_new(out/'DIRECT_RESPONSE_RESULTS.json',dict(rows=results,development_only=True,full_qualification_not_predicted=True))
    write_new(out/'CURVE_RESPONSE_RESULTS.json',dict(rows=curve_results,cost_consistency=consistency,no_future_feedback=True,not_a_validated_Markov_simulator=True))
    frozen=dict(schema='v8.E.common_out0_F1_frozen_ridge_bundle.v1',direct_models=all_models,curve_models=curve_models,feature_names=FEATURE_NAMES,menu=index['menu'],dataset_files_sha256=contract['dataset_files_sha256'],dataset_manifest_sha256=contract['dataset_manifest_sha256'],source_manifest_sha256=approval['source_manifest_sha256'],all_development_freeze=True,no_CV_best_model_selection=True,planner_control_authorization=False,window_cost_grants_task_qualification=False)
    write_new(out/'FROZEN_F1_BUNDLE.json',frozen)
    return dict(status='PASS_FIXED_F1_253_SOLVES_DEVELOPMENT_ONLY',counters=work.c,direct_result_rows=len(results),curve_result_rows=len(curve_results),frozen_bundle_sha256=sha(out/'FROZEN_F1_BUNDLE.json'),full_task_qualification_granted=False,independent_population_generalization=False,F2_neural_executed=False)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',required=True);p.add_argument('--approval',required=True);p.add_argument('--approval-sha256',required=True);args=p.parse_args()
    start=time.monotonic();cpu=time.process_time();root=Path(args.package).resolve();need(root==PACKAGE.resolve(),'UNIQUE_PACKAGE')
    ap=(root/args.approval).resolve();need(ap.is_relative_to(root) and sha(ap)==args.approval_sha256,'EXACT_MAIN_APPROVAL_SHA');approval=load(ap)
    need(approval.get('schema')=='v8.E.common_out0_F1_fit_approval.v1' and approval.get('status')=='APPROVED_BY_MAIN_AGENT' and approval.get('operation')=='F1_FIXED_RIDGE_ONLY' and approval.get('main_approval_id'),'SEPARATE_ACTUAL_F1_APPROVAL_REQUIRED')
    need(approval.get('activation_id')==ACTIVATION and approval.get('global_deadline_unix')==STOP and approval.get('output_directory')==OUT_REL,'ORIGINAL_GLOBAL_CLOCK_AND_OUTPUT')
    need(approval.get('source_manifest_path')==SOURCE_REL and sha(root/SOURCE_REL)==approval['source_manifest_sha256'],'F1_SOURCE_BINDING')
    need(approval.get('fit_contract_path')==CONTRACT_REL and sha(root/CONTRACT_REL)==approval['fit_contract_sha256'],'ACTUAL_DATA_CONTRACT_BINDING')
    source=load(root/SOURCE_REL)
    for rel,expected in source['files_sha256'].items():need(sha(root/rel)==expected,'FROZEN_F1_SOURCE_OR_DATA_CHANGED:'+rel)
    contract=load(root/CONTRACT_REL);need(approval.get('resources')==contract['resources'],'EXACT_REGISTERED_RESOURCE_BUDGET')
    need(time.time()<STOP,'GLOBAL_STOP');a=load(root/'ACTIVATION.json');need(a['activation_id']==ACTIVATION and a['hard_stop_unix']==STOP,'ACTIVATION_IDENTITY')
    out=root/OUT_REL;need(not out.exists(),'ONE_SHOT_F1_OUTPUT_NO_RETRY');out.mkdir(parents=True)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
    resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824));resource.setrlimit(resource.RLIMIT_CPU,(180,181));deadline=start+180.;work=Work(out,deadline)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('ORIGINAL_F1_180S_CAP')));signal.setitimer(signal.ITIMER_REAL,min(deadline-time.monotonic(),STOP-time.time()))
    write_new(out/'RUN_START.json',dict(status='START_APPROVED_F1_ONLY',pid=os.getpid(),actual_python=str(Path(sys.executable).resolve()),python_binary_sha256=sha(Path(sys.executable).resolve()),python_version=platform.python_version(),approval_sha256=args.approval_sha256,created_unix=time.time()))
    try:
        import numpy as np
        np.seterr(over='raise',invalid='raise');answer=perform(root,out,approval,work,np)
        for rel,expected in source['files_sha256'].items():need(sha(root/rel)==expected,'SOURCE_OR_DATA_CHANGED_DURING_FIT:'+rel)
        work.guard();answer.update(wall_s=time.monotonic()-start,cpu_s=time.process_time()-cpu,RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,numpy_version=np.__version__,numpy_module=str(Path(np.__file__).resolve()),physics=0,sealed_reads=0)
        write_new(out/'RUN_END.json',answer);print(json.dumps(answer,allow_nan=False))
    except BaseException as exc:
        write_new(out/'RUN_FAILED.json',dict(status='FAILED_PAID_WORK_PRESERVED_NO_AUTORETRY',error_type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc(),counters=work.c,wall_s=time.monotonic()-start,cpu_s=time.process_time()-cpu,RSS_peak_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,physics=0));raise
    finally:signal.setitimer(signal.ITIMER_REAL,0)

if __name__=='__main__':main()
