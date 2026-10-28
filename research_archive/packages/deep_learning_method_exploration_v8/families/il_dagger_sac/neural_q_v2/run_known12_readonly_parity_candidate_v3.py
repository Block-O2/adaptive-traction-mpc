"""SOURCE_ONLY：known12冻结开发parity；无旧head、新训练、物理或sealed读取。"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import resource
import signal
import sys
import time

STOP=1793114740.
ROOT='families/il_dagger_sac/neural_q_v2/'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text())
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def save(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def bounded(P,relative):
    q=(P/relative).resolve();assert q.is_relative_to(P)
    return q


def document(P,item):
    q=bounded(P,item['path']);assert sha(q)==item['sha256'],'FROZEN_PARITY_ARTIFACT_CHANGED:'+item['path']
    return load(q)


def usage():
    r=resource.getrusage(resource.RUSAGE_SELF)
    return {'wall_unix':time.time(),'CPU_user_s':r.ru_utime,'CPU_system_s':r.ru_stime,'RSS_peak_KiB':r.ru_maxrss,
            'PID':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),
            'python':sys.executable,'resolved_binary':str(Path(sys.executable).resolve()),'python_binary_sha256':sha(Path(sys.executable).resolve()),
            'actual_affinity':sorted(os.sched_getaffinity(0))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',required=True);parser.add_argument('--approval',required=True)
    parser.add_argument('--approval-sha',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();P=Path(args.package).resolve();initial=usage()
    ap=bounded(P,args.approval);assert sha(ap)==args.approval_sha
    a=load(ap)
    assert a['schema']=='v8.neuralq.readonly_fixed_models_authorization.v3'
    assert a['status']=='APPROVED_BY_MAIN_AGENT_FOR_NEURALQ_READ_ONLY_FIXED_MODELS_V3'
    assert a['scope']=='READ_ONLY_KNOWN_REPLAY_PARITY' and a['training_or_physics_authorized'] is False
    assert a['approved_unix']<=initial['wall_unix']<a['expires_unix']<=min(initial['wall_unix']+30.,STOP)
    assert a['maximum_wall_s']==a['maximum_CPU_s']==30 and a['maximum_AS_bytes']==1024**3
    assert a['runner_source_sha256']==sha(__file__) and a['expected_binary_sha256']==initial['python_binary_sha256']
    assert sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE')=='1'
    assert len(initial['actual_affinity'])==1,'SINGLE_CPU_EXTERNAL_LAUNCH_REQUIRED'
    for n in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):assert os.environ.get(n)=='1'
    parity_manifest=document(P,a['parity_source_manifest']);contract=document(P,a['parity_contract'])
    assert contract['runner_source_sha256']==sha(__file__)
    assert contract['parity_source_manifest_sha256']==a['parity_source_manifest']['sha256']
    assert contract['readonly_source_manifest_sha256']==a['source_manifest_sha256']
    for relative,h in parity_manifest['required_files_sha256'].items():assert sha(bounded(P,relative))==h
    readonly=document(P,parity_manifest['readonly_manifest']);assert a['source_manifest_sha256']==parity_manifest['readonly_manifest']['sha256']
    assert a['bundle_file_sha256']==readonly['bundle']['sha256']
    original_readonly_contract=document(P,a['readonly_contract'])
    assert original_readonly_contract['source_manifest_sha256']==a['source_manifest_sha256']
    contexts=document(P,parity_manifest['context25_input']);reference=document(P,parity_manifest['stored_reference'])
    assert a['known_context25_sha256']==parity_manifest['context25_input']['sha256']
    assert a['stored_reference_sha256']==parity_manifest['stored_reference']['sha256']
    assert contexts['schema']=='v8.neuralq.known12_scoped_context25_for_parity.v3'
    assert reference['schema']=='v8.neuralq.known12_stored_prediction_and_choice_reference.v3'
    assert digest(contexts['feature_names'])==a['feature_names_sha256'] and len(contexts['feature_names'])==25
    cases=contexts['cases'];assert len(cases)==12 and len({c['case_join_key_evaluation_only'] for c in cases})==12
    assert {c['case_join_key_evaluation_only'] for c in cases}==set(reference['cases'])
    for c in cases:assert len(c['features25'])==25 and all(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) for v in c['features25'])
    for relative,h in reference['reference_sources_sha256'].items():assert sha(bounded(P,relative))==h
    document_models=document(P,readonly['bundle'])
    out=Path(args.output).resolve();assert out.is_relative_to(P/ROOT) and not out.exists(),'NEW_PRIVATE_OUTPUT_NO_RETRY'
    out.mkdir()
    save(out/'START.json',{'process':initial,'approval_sha256':args.approval_sha,'expires_unix':a['expires_unix'],
         'scope':'KNOWN_FROZEN_DEVELOPMENT_ONLY_NOT_RUNTIME_PROOF_OR_UNSEEN_VALIDATION','real_fit_physics':0})
    resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(30,31))
    def timeout(signum,frame):raise TimeoutError('ORIGINAL_READONLY_PARITY_LOCAL_OR_GLOBAL_STOP')
    signal.signal(signal.SIGALRM,timeout);signal.signal(signal.SIGXCPU,timeout)
    signal.setitimer(signal.ITIMER_REAL,max(.001,min(a['expires_unix'],STOP)-time.time()))
    accounting={};current={};completed=[];comparisons=[]
    try:
        path=bounded(P,readonly['api']['path']);assert sha(path)==readonly['api']['sha256']
        spec=importlib.util.spec_from_file_location('_known12_readonly_parity_api_v3',path)
        api=importlib.util.module_from_spec(spec);spec.loader.exec_module(api)
        assert Path(api.__file__).resolve()==path
        accounting['batch_restore_entry']=1
        restored=api.restore_fixed(document_models,authority=a,expected_bundle_object_sha256=readonly['bundle_object_sha256'],
                                   expected_source_manifest_sha256=a['source_manifest_sha256'],accounting=accounting)
        accounting['batch_restore_completed']=1
        numpy=sys.modules['numpy']
        save(out/'NUMPY_AFTER_RESTORE_BEFORE_FIRST_FORWARD.json',{'version':numpy.__version__,'file':numpy.__file__,
             'module_sha256':sha(numpy.__file__),'process':usage(),'old_training_head_imported':False})
        def add_local(local):
            for k,v in local.items():
                assert isinstance(v,int) and not isinstance(v,bool)
                accounting[k]=accounting.get(k,0)+v
        for case in cases:
            join=case['case_join_key_evaluation_only'];current={'case_join_evaluation_only':join,'phase':'PREDICT','local_paid_prefix':{}}
            # The only model input is the frozen 25-vector and whitelist names.
            # No case hash, reference vector, choice, or physical label is passed.
            local=current['local_paid_prefix'];accounting['batch_predict_entry']=accounting.get('batch_predict_entry',0)+1
            try:
                answer=api.predict_fixed(restored,contexts['feature_names'],case['features25'],qa_validated=True,authority=a,accounting=local)
            except BaseException:
                add_local(local);current['local_paid_prefix_already_aggregated']=True;raise
            add_local(local);accounting['batch_predict_completed']=accounting.get('batch_predict_completed',0)+1
            current['phase']='COMPARE_STORED_ONLY';expected=reference['cases'][join]
            assert set(answer['all_head_values'])==set(expected['expected_outputs']) and len(expected['expected_outputs'])==63
            maximum_return_risk=0.;maximum_physical=0.
            for mid,wanted in expected['expected_outputs'].items():
                actual=answer['all_head_values'][mid];assert len(actual)==len(wanted)==5
                target=mid.split('/')[1] if mid.startswith('RIDGE/') else mid.split('/')[2]
                tolerance=1e-9 if target in ('RETURN','RISK') else 1e-6
                for observed,old in zip(actual,wanted):
                    accounting['scalar_comparison_entry']=accounting.get('scalar_comparison_entry',0)+1
                    delta=abs(observed-old)
                    assert math.isfinite(delta) and delta<=tolerance,('OUTPUT_PARITY',join,mid,delta,tolerance)
                    accounting['scalar_comparison_completed']=accounting.get('scalar_comparison_completed',0)+1
                    if target in ('RETURN','RISK'):maximum_return_risk=max(maximum_return_risk,delta)
                    else:maximum_physical=max(maximum_physical,delta)
            assert list(answer['decisions'])==readonly['selectors'] and set(expected['expected_choices'])==set(readonly['selectors'])
            for label,wanted in expected['expected_choices'].items():
                accounting['choice_comparison_entry']=accounting.get('choice_comparison_entry',0)+1
                actual=answer['decisions'][label]
                assert actual['action_index']==wanted['action_index'],('CHOICE_PARITY',join,label,actual['action_index'],wanted['action_index'])
                assert actual['execution_fallback_B_predeclared']==wanted['B_fallback'],('FALLBACK_PARITY',join,label)
                accounting['choice_comparison_completed']=accounting.get('choice_comparison_completed',0)+1
            comparisons.append({'case_join_evaluation_only':join,'max_RETURN_RISK_abs_error':maximum_return_risk,
                                'max_physical_abs_error':maximum_physical,'output_scalars':315,'choice_and_fallback_exact':68})
            completed.append(join);current={}
        expected_counts={'batch_restore_entry':1,'batch_restore_completed':1,'model_restore_entry':63,'model_restore_completed':63,
             'logical_model_deepcopy_entry':63,'logical_model_deepcopy_completed':63,'completed_parameter_array_constructions':195,
             'completed_input_normalization_array_constructions':2,'batch_predict_entry':12,'batch_predict_completed':12,
             'head_forward_entry':720,'head_forward_completed':720,'ridge_forward_entry':36,'ridge_forward_completed':36,
             'completed_matrix_products':1260,'completed_tanh':360,'completed_sigmoid':216,
             'scalar_comparison_entry':3780,'scalar_comparison_completed':3780,'choice_comparison_entry':816,'choice_comparison_completed':816}
        assert accounting==expected_counts,('EXACT_PARITY_ACCOUNTING',accounting,expected_counts)
        save(out/'RESULT.json',{'status':'PASS_KNOWN12_READONLY_NUMERIC_AND_CHOICE_PARITY_NOT_UNSEEN_VALIDATION_OR_DEPLOYMENT_PERMISSION',
             'START':initial,'END':usage(),'accounting':accounting,'expected_accounting':expected_counts,'comparisons':comparisons,
             'reference_kind_accounting':reference['source_reference_kinds'],'reference_original_physical_JF_objective_not_returnfloor':True,
             'old_training_head_import_forward_restore_fit':0,'new_gradient_fit_physics':0,'sealed_Beta_or_selected_validation_reads':0})
    except BaseException as error:
        signal.setitimer(signal.ITIMER_REAL,0.)
        save(out/'FAILED_PARITY_PAID_PREFIX_V3.json',{'status':'FAILED_OR_INCOMPLETE_NO_RETRY','error_type':type(error).__name__,
             'error':str(error),'START':initial,'END':usage(),'accounting':accounting,'completed_cases':completed,'current':current,
             'partial_suboperation_work':'UNKNOWN_BOUNDED_NOT_ZERO_IF_NO_COMPLETION','old_head_forward_fit_physics':0,
             'automatic_retry_authorized':False})
        raise
    finally:signal.setitimer(signal.ITIMER_REAL,0.)


if __name__=='__main__':main()
