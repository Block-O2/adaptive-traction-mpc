"""Bounded actual-model benchmark consumer; never starts scientific rollouts."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from latency_benchmark_models import benchmark_models
from value_models import load_model
import numpy as np


def main():
    root=Path(__file__).resolve().parents[4]
    doc=root/'stages/stage5_personalized_motion_learning/docs/value_learning_research_v1'
    raw=root/'stages/stage5_personalized_motion_learning/results/value_learning_research_v1/latency_cpu_models_v1'
    output=raw/'CPU_MODEL_LATENCY.json'
    if output.exists():raise FileExistsError(output)
    contract=json.loads((doc/'LEARNING_RESEARCH_V1_CONTRACT.json').read_text())
    cutoff=datetime.fromisoformat(contract['hard_deadline_utc'])
    started=datetime.now(timezone.utc)
    comparison=doc/'OFFLINE_VALUE_MODEL_COMPARISON.json'
    previous=None
    while not comparison.exists():
        if datetime.now(timezone.utc)>=cutoff:raise RuntimeError('hard campaign deadline before actual models ready')
        branches=doc/'ONE_STEP_BRANCH_RESULTS.json'
        count=len(json.loads(branches.read_text())) if branches.exists() else 0
        if count!=previous:
            print(json.dumps({'waiting_for_actual_selected_models':True,'branch_attempts':count}),flush=True)
            previous=count
        time.sleep(30)
    report=json.loads(comparison.read_text())
    manifest=json.loads((doc/'VALUE_DATASET_MANIFEST.json').read_text())
    dataset=root/manifest['dataset_path']/'data.npz'
    with np.load(dataset,allow_pickle=False) as arrays:X=arrays['X'].copy()
    models={};model_hashes={};load_ms={};model_paths={}
    for key in ('ridge_full','mlp_full'):
        path=Path(report['selected_models'][key]['model_path'])
        actual=hashlib.sha256(path.read_bytes()).hexdigest()
        if actual!=report['selected_models'][key]['sha256']:raise ValueError('selected model hash mismatch:'+key)
        before=time.perf_counter_ns();models[key]=load_model(path);load_ms[key]=(time.perf_counter_ns()-before)/1e6
        model_hashes[key]=actual;model_paths[key]=str(path)
    measured=datetime.now(timezone.utc)
    result=benchmark_models(models,X,counts=(1,4,8,16,32),repeats=500,warmup=30)
    result.update(wait_started_utc=started.isoformat(),benchmark_started_utc=measured.isoformat(),
                  benchmark_finished_utc=datetime.now(timezone.utc).isoformat(),
                  model_load_first_call_ms=load_ms,model_file_sha256=model_hashes,model_paths=model_paths,
                  feature_file_path=str(dataset),feature_file_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
                  comparison_sha256=hashlib.sha256(comparison.read_bytes()).hexdigest(),
                  selection='validation-selected ridge_full and mlp_full; no accuracy/model retuning in benchmark',
                  concurrent_load_caveat='campaign search/branch jobs may be active; descriptive CPU timings preserve resulting outliers',
                  runtime_assurance_status='RUNTIME_ASSURANCE_REQUIRED_BEFORE_HARDWARE_EXPERIMENTS')
    raw.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'cpu_model_benchmark_complete':True,'output':str(output),
                      'models':{key:rows[2] for key,rows in result['models'].items()}},indent=2),flush=True)


if __name__=='__main__':main()
