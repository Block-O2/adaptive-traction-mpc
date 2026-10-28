"""Benchmark actual trained models, including CPU feature transfer/batching.

Call benchmark_models({'ridge': model, 'mlp': model}, X) where predict(X) is
the production research model API and X consists of actual recorded features.
This measures model stages only; no full-decision latency claim is made.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
from time import perf_counter_ns
import numpy as np
from latency_tools import distribution


def benchmark_models(models, X, *, counts=(1,4,8,16,32), repeats=500, warmup=30):
    features = np.asarray(X,dtype=float)
    if features.ndim != 2 or not len(features) or not np.all(np.isfinite(features)):
        raise ValueError("actual feature matrix must be finite nonempty 2D")
    if repeats < 2 or warmup < 0:
        raise ValueError("invalid benchmark repetition count")
    output={"schema":"actual_value_model_cpu_benchmark_v1",
            "evidence_category":"descriptive_model_microbenchmark",
            "model_input_source":"actual recorded feature matrix; no synthetic update proxy",
            "feature_count":features.shape[1],"feature_rows":len(features),
            "feature_bytes_sha256":hashlib.sha256(features.astype('<f8').tobytes()).hexdigest(),
            "environment":{"platform":platform.platform(),"processor":platform.processor(),
                           "python":platform.python_version(),"numpy":np.__version__,
                           "thread_env":{k:os.environ.get(k) for k in
                               ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}},
            "models":{},"full_decision_latency_measured":False,
            "gpu":{"status":"NOT_BENCHMARKED","reason":"NumPy CPU model architecture; GPU is optional"}}
    for name,model in models.items():
        rows=[]
        for count in counts:
            if count < 1: raise ValueError("candidate count must be positive")
            batch=np.resize(features,(count,features.shape[1])).copy()
            started=perf_counter_ns();first=model.predict(batch);cold=(perf_counter_ns()-started)/1e6
            if np.asarray(first).shape != (count,) or not np.all(np.isfinite(first)):
                raise ValueError("model output must be finite scalar per candidate")
            for _ in range(warmup): model.predict(batch)
            infer=[];copy_ms=[];copy_infer=[];unbatched=[]
            for _ in range(repeats):
                started=perf_counter_ns();model.predict(batch);infer.append((perf_counter_ns()-started)/1e6)
                started=perf_counter_ns();copied=np.array(batch,dtype=float,copy=True);copy_ms.append((perf_counter_ns()-started)/1e6)
                started=perf_counter_ns();model.predict(np.array(batch,dtype=float,copy=True));copy_infer.append((perf_counter_ns()-started)/1e6)
                started=perf_counter_ns()
                for item in batch: model.predict(item[None,:])
                unbatched.append((perf_counter_ns()-started)/1e6)
            rows.append({"candidate_count":count,"repeats":repeats,"warmup_calls":warmup,
                         "first_call_ms":cold,"cold_definition":"first call at this candidate batch size after model load; not process-cold",
                         "warm_batched_predict_ms":distribution(infer),
                         "cpu_input_copy_ms":distribution(copy_ms),
                         "cpu_input_copy_and_batched_predict_ms":distribution(copy_infer),
                         "unbatched_per_candidate_predict_total_ms":distribution(unbatched)})
        output['models'][name]=rows
    return output


def time_actual_update(operation, *args, **kwargs):
    """Return actual model/result and duration; callers preserve update provenance."""
    started=perf_counter_ns()
    result=operation(*args,**kwargs)
    return result,(perf_counter_ns()-started)/1e6


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',action='append',required=True,help='name=actual model NPZ path')
    parser.add_argument('--features',type=Path,required=True,help='NPZ containing actual X matrix')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=500)
    parser.add_argument('--counts',default='1,4,8,16,32')
    args=parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    from value_models import load_model
    models={};hashes={};load_times={}
    for item in args.model:
        name,path=item.split('=',1)
        started=perf_counter_ns();models[name]=load_model(path);load_times[name]=(perf_counter_ns()-started)/1e6
        hashes[name]=hashlib.sha256(Path(path).read_bytes()).hexdigest()
    with np.load(args.features,allow_pickle=False) as data: X=data['X']
    result=benchmark_models(models,X,counts=tuple(map(int,args.counts.split(','))),repeats=args.repeats)
    result['model_file_sha256']=hashes
    result['model_load_first_call_ms']=load_times
    result['feature_file_sha256']=hashlib.sha256(args.features.read_bytes()).hexdigest()
    result['argv']=vars(args)|{'features':str(args.features),'output':str(args.output)}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({name:rows[min(2,len(rows)-1)] for name,rows in result['models'].items()},indent=2))


if __name__=='__main__':main()
