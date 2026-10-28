"""E2 SOURCE_ONLY domain-aligned surrogate runner; no fitting on import.

Requires a separate exact actual-data/source-bound main approval. No physics,
planner control or future-B reconstruction. Paired wrench integrals are N/A.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import platform
import resource
import signal
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
REL='families/learning_assisted/common_out0_v2/'
DATA=REL+'data/fulltask_e2_v1/';OUT=REL+'fits/e2_v1'
SOURCE=REL+'FIT_E2_SOURCE_MANIFEST_V1.json';CONTRACT=REL+'FIT_E2_FROZEN_CONTRACT_V1.json'
ACTIVATION='deep_learning_method_exploration_v8_20261027T032540Z';STOP=1793114740.
DOMAINS={'D4':[.5,1.,1.5,2.,2.5,3.,3.5,4.],'DFull':[.5,1.,2.,4.,8.,12.,16.,19.03]}
RIDGE=('RIDGE_ACTION_BLIND39','RIDGE_ACTION_ONLY','RIDGE_CONTEXT_ACTION','RIDGE_PAIRED')
NEURAL=('MLP_ACTION_ONLY','MLP_CONTEXT_ACTION','MLP_PAIRED')
NPZ_KEYS={'endpoint14','window_JF_JM','dense14','dense_cost_JF_JM','dense_actual_elapsed_s','dense_public_query_s','horizons_s'}
EXPECTED=dict(input_normalizer_fits=11,target_scaling_fits=770,matrix_solve_attempts=704,matrix_solve_successes=704,scalar_head_solutions_attempted=11264,linear_design_training_rows=30720,neural_initialization_attempts=66,neural_initializations=66,gradient_update_attempts=13200,parameter_gradient_updates=13200,network_training_forward_API_calls=17600,network_training_forward_query_vectors=2252800,network_backward_API_calls=17600,network_backward_query_vectors=2252800,shared_B_training_forward_API_calls=4400,shared_B_backward_API_calls=4400,shared_B_inference_forward_API_calls=192,prediction_API_calls=2240,prediction_query_vectors=5853696,trajectory_prediction_requests=1344,fixed_baseline_query_vectors=1461888,physics=0)


def need(test,reason):
    if not test:raise ValueError(reason)
def load(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def clean(o):
    if isinstance(o,dict):return {str(k):clean(v) for k,v in o.items()}
    if isinstance(o,(tuple,list)):return [clean(v) for v in o]
    if hasattr(o,'tolist'):return clean(o.tolist())
    return o
def new(p,o):
    with Path(p).open('x') as f:json.dump(clean(o),f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def append(p,o):
    with Path(p).open('a') as f:f.write(json.dumps(clean(o),sort_keys=True,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


class Work:
    def __init__(self,out,deadline):
        self.out=out;self.deadline=deadline;self.c={key:0 for key in EXPECTED};self.current_neural_state=None;self.prediction_kinds={}
    def guard(self):need(time.monotonic()<self.deadline and time.time()<STOP,'E2_UNCHANGED_LOCAL_GLOBAL_DEADLINE')
    def event(self,kind,**payload):self.guard();append(self.out/'WORK_EVENTS.jsonl',dict(event=kind,unix=time.time(),counters=self.c.copy(),**payload))
    def prediction(self,kind,count):
        self.guard();self.c['prediction_API_calls']+=1;self.c['prediction_query_vectors']+=count
        need(self.c['prediction_query_vectors']<=6000000,'E2_PREDICTION_QUERY_CAP')
        item=self.prediction_kinds.setdefault(kind,dict(API_calls=0,query_vectors=0));item['API_calls']+=1;item['query_vectors']+=count


def perform(root,out,approval,work,np):
    from common_out0_interface_v1 import FEATURE_NAMES
    from fit_f1_candidate_v1 import score_response,baseline16
    import e2_models_candidate_v1 as models
    index=load(root/DATA/'INDEX.json');manifest=load(root/DATA/'DATASET_MANIFEST.json');receipt=load(root/DATA/'BUILD_EXECUTION_RECEIPT.json')
    need(index['schema']=='v8.E.common_out0_fulltask_e2_index.v1' and index['feature_names']==FEATURE_NAMES,'E2_DATA_SCHEMA_FEATURES')
    need(manifest['schema']=='v8.E.common_out0_fulltask_e2_dataset_manifest.v1' and manifest['status']=='BUILT_ORIGINAL_SOURCE_BOUND_NO_FIT' and receipt['status']=='PASS_FULLTASK_E2_ONE_SHOT_DATASET_BUILD_NO_FIT','E2_ACTUAL_APPROVED_BUILD')
    need(manifest['F1_prefix_label_SHA_verified_rows']==48 and manifest['full_TASK_boundary_nodes']==3807 and manifest['dense_labels_training_authorized'] is False,'E2_PRESERVED_F1_COMPLETE_TASK_NO_DENSE_TRAINING')
    with np.load(root/DATA/'TARGETS_CAUSAL_ONLY.npz',allow_pickle=False) as f:
        need(set(f.files)==NPZ_KEYS,'E2_LABEL_ALLOWLIST');data={key:f[key] for key in NPZ_KEYS}
    rows=index['rows'];x=np.asarray([r['input']['features'] for r in rows],float);actions=np.asarray([r['input']['recipe_index'] for r in rows],int)
    cases=[r['evaluation_only']['case_sha256'] for r in rows];unique=sorted(set(cases));times=data['dense_public_query_s'];horizons=data['horizons_s'];horizon_ix=(horizons/.005).round().astype(int)
    need(len(rows)==48 and len(unique)==10 and x.shape==(48,39) and data['dense14'].shape==(48,3807,14),'E2_48_CASES_SHAPES')
    need(np.array_equal(times,np.arange(3807)*.005) and np.array_equal(horizons,np.array([.5,1.,2.,4.,8.,12.,16.,19.03])),'E2_PUBLIC_QUERY_DOMAIN')
    initial=np.c_[x[:,25:39],np.zeros((48,2))];need(np.array_equal(initial[:,:14],data['dense14'][:,0]),'E2_PREACTION_ANCHOR')
    truth=np.concatenate([data['dense14'],data['dense_cost_JF_JM']],axis=2);paired_truth=truth.copy()
    for case in unique:
        ids=[i for i,c in enumerate(cases) if c==case];b=next(i for i in ids if actions[i]==0)
        need(all(np.array_equal(x[i],x[b]) for i in ids),'E2_SAME_PARENT_COMMON39');paired_truth[ids]-=truth[b]
    direct_results=[];integrated_results=[];consistency=[];all_models={};initial_identity={};normalizers={}
    unit=np.r_[np.full(8,180./math.pi),np.ones(8)]

    def record_curves(test,forecasts,label,domain,kind,paired):
        direct=np.asarray([p[horizon_ix] for p in forecasts]);absolute_integrals=[];errors=[]
        for position,i in enumerate(test):
            p=forecasts[position];target=paired_truth[i] if paired else truth[i];err=(p-target)*unit;items=[]
            if paired:integral=None
            else:
                intervals=np.c_[np.linalg.norm(p[:-1,8:11],axis=1),np.linalg.norm(p[:-1,11:14],axis=1)]*.005
                integral=np.vstack([np.zeros((1,2)),np.cumsum(intervals,axis=0)]);absolute_integrals.append(np.c_[p[horizon_ix,:14],integral[horizon_ix]])
            for h,k in zip(horizons,horizon_ix):
                items.append(dict(horizon_s=float(h),query_within_training_time_domain=bool(h<=max(DOMAINS[domain])),channel_MAE_to_h=abs(err[:k+1]).mean(axis=0).tolist(),endpoint_abs_error=abs(err[k]).tolist(),direct_cost_heads=p[k,14:].tolist(),integrated_absolute_wrench_cost=None if paired else integral[k].tolist(),paired_wrench_integral_status='NOT_APPLICABLE_DELTA_WRENCH_NORM_IS_NOT_DELTA_COST' if paired else 'ABSOLUTE_PREDICTED_WRENCH_ORIGINAL_LEFT_RULE'))
            errors.append(dict(id=rows[i]['id'],target_semantics='DELTA14_AND_INDEPENDENT_DELTA_JF_JM' if paired else 'ABSOLUTE14_AND_INDEPENDENT_JF_JM',errors=items,future_B_trajectory_used_in_inference=False,future_feedback=False))
        append(out/'TRAJECTORY_ERRORS.jsonl',dict(fold=label,domain=domain,method=kind,rows=errors))
        for j,h in enumerate(horizons):
            direct_rows=score_response(test,direct[:,j],truth[test,horizon_ix[j]],rows,paired,work,np)
            direct_results.extend(dict(fold=label,domain=domain,method=kind,horizon_s=float(h),**r) for r in direct_rows)
            if not paired:
                integrated_rows=score_response(test,np.asarray(absolute_integrals)[:,j],truth[test,horizon_ix[j]],rows,False,work,np)
                integrated_results.extend(dict(fold=label,domain=domain,method=kind,horizon_s=float(h),**r) for r in integrated_rows)
                for a,b in zip(direct_rows,integrated_rows):
                    need(a['case_sha256_evaluation_only']==b['case_sha256_evaluation_only'],'E2_MATCHED_INTEGRAL_DIAGNOSTIC')
                    consistency.append(dict(fold=label,domain=domain,method=kind,horizon_s=float(h),case_sha256_evaluation_only=a['case_sha256_evaluation_only'],deltaJF_head_minus_integrated=(np.asarray(a['paired_JF_prediction_N_s'])-np.asarray(b['paired_JF_prediction_N_s'])).tolist(),deltaJM_head_minus_integrated=(np.asarray(a['paired_JM_prediction_Nm_s'])-np.asarray(b['paired_JM_prediction_Nm_s'])).tolist()))

    for held in [None]+unique:
        work.guard();label='ALL_DEVELOPMENT' if held is None else 'LEAVE_CASE_'+held
        train=[i for i,c in enumerate(cases) if c!=held];test=list(range(48)) if held is None else [i for i,c in enumerate(cases) if c==held]
        representatives=[next(i for i in train if cases[i]==c) for c in unique if c!=held]
        center=x[representatives].mean(axis=0);scale=x[representatives].std(axis=0);scale=np.where(scale<1e-9,1.,scale);z=(x-center)/scale;work.c['input_normalizer_fits']+=1
        normalizer=dict(center=center.tolist(),scale=scale.tolist(),train_unique_cases=len(representatives),fit_case_once_not_action_time_repeats=True);normalizers[label]=normalizer
        for domain,knot_times in DOMAINS.items():
            nodes=(np.asarray(knot_times)/.005).round().astype(int);knots=np.r_[0.,knot_times]
            for kind in RIDGE:
                ispaired=kind=='RIDGE_PAIRED';design=models.ridge_design(z,actions,kind,np);target=paired_truth if ispaired else truth
                predictions=np.zeros((len(test),9,16));predictions[:,0]=0. if ispaired else initial[test];node_models=[]
                for j,node in enumerate(nodes):
                    work.c['target_scaling_fits']+=1;model=models.fit_ridge(design[train],target[train,node],paired=ispaired,work=work,label=label+'/'+domain+'/'+kind+'/'+str(knot_times[j]),np=np)
                    node_models.append(model);predictions[:,j+1]=models.predict_knots(design[test],model,work,np)
                    append(out/'MODEL_SNAPSHOTS.jsonl',dict(fold=label,domain=domain,method=kind,knot_s=knot_times[j],model=model,normalizer=normalizer))
                forecasts=[]
                for pos,i in enumerate(test):
                    work.c['trajectory_prediction_requests']+=1;p=models.interpolate_knots(times,knots,predictions[pos],work,np)
                    need(np.array_equal(p[0],np.zeros(16) if ispaired else initial[i]),'E2_RIDGE_INITIAL_ANCHOR');forecasts.append(p)
                record_curves(test,forecasts,label,domain,kind,ispaired)
                if held is None:all_models[domain+'/'+kind]=dict(kind=kind,paired=ispaired,knot_times_s=knot_times,node_models=node_models,normalizer=normalizer,interpolation='piecewise linear; last interval extrapolation explicit OOD')
            train_z=np.repeat(z[train],8,axis=0);train_a=np.repeat(actions[train],8);train_t=np.tile(np.asarray(knot_times),len(train));train_initial=np.repeat(initial[train],8,axis=0)
            for kind in NEURAL:
                ispaired=kind=='MLP_PAIRED';target=(paired_truth if ispaired else truth)[train][:,nodes].reshape(-1,16);work.c['target_scaling_fits']+=1
                model=models.fit_mlp(train_z,train_a,train_t,target,train_initial,kind=kind,work=work,label=label+'/'+domain+'/'+kind,np=np)
                key=label+'/'+kind
                if domain=='D4':initial_identity[key]=model['initial_weights_sha256']
                else:need(initial_identity[key]==model['initial_weights_sha256'],'E2_MATCHED_DOMAIN_INITIAL_WEIGHTS')
                append(out/'MODEL_SNAPSHOTS.jsonl',dict(fold=label,domain=domain,method=kind,model=model,normalizer=normalizer));forecasts=[]
                for i in test:
                    work.c['trajectory_prediction_requests']+=1;p=models.predict_mlp(np.repeat(z[i:i+1],len(times),axis=0),np.full(len(times),actions[i],int),times,np.repeat(initial[i:i+1],len(times),axis=0),model,work,np)
                    need(np.array_equal(p[0],np.zeros(16) if ispaired else initial[i]),'E2_NEURAL_INITIAL_ANCHOR')
                    if ispaired and actions[i]==0:need(np.array_equal(p,np.zeros_like(p)),'E2_PAIRED_B_ZERO_ALL_QUERY_TIMES')
                    forecasts.append(p)
                record_curves(test,forecasts,label,domain,kind,ispaired)
                if held is None:all_models[domain+'/'+kind]=dict(model=model,normalizer=normalizer)
            for kind,kinematic in [('PERSISTENCE',False),('KINEMATIC',True)]:
                forecasts=[]
                for i in test:
                    work.c['fixed_baseline_query_vectors']+=len(times);forecasts.append(baseline16(np.repeat(x[i:i+1],len(times),axis=0),times,kinematic,np))
                record_curves(test,forecasts,label,domain,kind,False)
        work.event('FOLD_COMPLETE',fold=label)
    need(work.c==EXPECTED,'E2_EXACT_PREREGISTERED_COMPLETE_WORK_COUNTS:'+str(work.c))
    new(out/'DIRECT_HEAD_RESULTS.json',dict(rows=direct_results,qualification_retrospective_only=True,no_future_masks=True))
    new(out/'ABSOLUTE_WRENCH_INTEGRAL_RESULTS.json',dict(rows=integrated_results,cost_head_consistency=consistency,paired_integrals='NOT_APPLICABLE_NO_FUTURE_TRUE_B_RECONSTRUCTION',norm_delta_wrench_not_delta_cost=True))
    frozen=dict(schema='v8.E.E2_frozen_conditional_trajectory_surrogates.v1',feature_names=FEATURE_NAMES,menu=index['menu'],all_development_models=all_models,source_manifest_sha256=approval['source_manifest_sha256'],dataset_sha256=load(root/CONTRACT)['dataset_files_sha256'],domains=DOMAINS,initial_anchor=True,public_time_scale_s=20.,conditional_trajectory_surrogate=True,Markov_simulator=False,PETS_reproduction=False,planner_control_authorization=False,qualification_from_cost=False,neural_loss_not_policy_reward=True,paired_outputs='delta14 and independent deltaJF/JM; absolute reconstruction from future B forbidden',CV_best_or_epoch_selection=False)
    for relative,expected in load(root/SOURCE)['files_sha256'].items():need(sha(root/relative)==expected,'E2_PRE_FREEZE_SOURCE_OR_DATA_CHANGED:'+relative)
    new(out/'FROZEN_E2_BUNDLE.json',frozen)
    return dict(status='PASS_E2_MATCHED_TIME_DOMAIN_SOURCE_BOUND_DEVELOPMENT_ONLY',counters=work.c,prediction_backend_kinds=work.prediction_kinds,direct_result_rows=len(direct_results),absolute_integral_result_rows=len(integrated_results),frozen_bundle_sha256=sha(out/'FROZEN_E2_BUNDLE.json'),new_physics=0,independent_patient_generalization=False,planner_control=False)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--package',required=True);parser.add_argument('--approval',required=True);parser.add_argument('--approval-sha256',required=True);args=parser.parse_args()
    start=time.monotonic();cpu=time.process_time();root=Path(args.package).resolve();need(root==ROOT.resolve(),'E2_UNIQUE_PACKAGE')
    path=(root/args.approval).resolve();need(path.is_relative_to(root) and sha(path)==args.approval_sha256,'E2_EXACT_ACTUAL_APPROVAL');approval=load(path)
    need(approval.get('schema')=='v8.E.E2_fit_approval.v1' and approval.get('status')=='APPROVED_BY_MAIN_AGENT' and approval.get('operation')=='E2_FIXED_DOMAIN_RIDGE_MLP_ONLY' and approval.get('main_approval_id'),'E2_SEPARATE_ACTUAL_FIT_APPROVAL_REQUIRED')
    need(approval.get('activation_id')==ACTIVATION and approval.get('global_deadline_unix')==STOP and approval.get('output_directory')==OUT,'E2_ORIGINAL_CLOCK_OUTPUT')
    need(approval.get('source_manifest_path')==SOURCE and sha(root/SOURCE)==approval['source_manifest_sha256'],'E2_SOURCE_BINDING')
    need(approval.get('fit_contract_path')==CONTRACT and sha(root/CONTRACT)==approval['fit_contract_sha256'],'E2_ACTUAL_DATA_CONTRACT')
    contract=load(root/CONTRACT);need(contract['expected_success_counters']==EXPECTED and contract['domains']==DOMAINS,'E2_REGISTERED_WORK_DOMAINS')
    need(approval['resources']==contract['resources'],'E2_EXACT_RESOURCE_APPROVAL')
    source=load(root/SOURCE)
    for rel,expected in source['files_sha256'].items():need(sha(root/rel)==expected,'E2_FROZEN_SOURCE_DATA_CHANGED:'+rel)
    activation=load(root/'ACTIVATION.json');need(activation['activation_id']==ACTIVATION and activation['hard_stop_unix']==STOP and time.time()<STOP,'E2_GLOBAL_STOP')
    for name,expected in contract['dataset_files_sha256'].items():need(sha(root/DATA/name)==expected,'E2_ACTUAL_DATA_BYTES:'+name)
    out=root/OUT;need(not out.exists(),'E2_ONE_SHOT_EXISTING_OUTPUT_NO_RETRY');out.mkdir(parents=True)
    os.environ.update(PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1');sys.dont_write_bytecode=True
    os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824));resource.setrlimit(resource.RLIMIT_CPU,(240,241))
    deadline=start+240.;work=Work(out,deadline);signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('E2_ORIGINAL_240S_CAP')));signal.setitimer(signal.ITIMER_REAL,min(deadline-time.monotonic(),STOP-time.time()))
    new(out/'RUN_START.json',dict(approval_sha256=args.approval_sha256,source_manifest_sha256=approval['source_manifest_sha256'],created_unix=time.time(),actual_python=str(Path(sys.executable).resolve()),actual_python_binary_sha256=sha(Path(sys.executable).resolve()),python_version=platform.python_version(),one_shot_no_retry=True))
    try:
        import numpy as np
        need(Path(np.__file__).resolve().is_relative_to(Path('/home/hank/ihear-lab/rl_b_cloud_v1/.venv/lib')),'E2_MAIN_VENV_NUMPY_REQUIRED')
        answer=perform(root,out,approval,work,np)
        for rel,expected in source['files_sha256'].items():need(sha(root/rel)==expected,'E2_SOURCE_DATA_CHANGED_DURING_FIT:'+rel)
        answer.update(wall_s=time.monotonic()-start,CPU_s=time.process_time()-cpu,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,numpy_version=np.__version__,numpy_module=str(Path(np.__file__).resolve()))
        new(out/'RUN_END.json',answer);print(json.dumps(answer,allow_nan=False))
    except BaseException as error:
        new(out/'RUN_FAILED.json',dict(status='FAILED_PRESERVED_NO_RETRY',error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),counters=work.c,prediction_kinds=work.prediction_kinds,unfinished_neural_state=work.current_neural_state,wall_s=time.monotonic()-start,CPU_s=time.process_time()-cpu,RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,physics=0));raise
    finally:signal.setitimer(signal.ITIMER_REAL,0.)


if __name__=='__main__':main()
