"""Read only preserved startup/boundary arrays; never run a plant interval."""
import json
from pathlib import Path
import numpy as np
from evidence_io import read_json

ROOT=Path(__file__).resolve().parents[4]
RAW=ROOT/'stages/stage5_personalized_motion_learning/results/value_learning_research_v1'
run=RAW/'runs/pilot_scratch_v1_rep_02/rep_01'
artifact=read_json(run/'runtime_artifacts.json')
print('ARTIFACT_KEYS',list(artifact))
for key,value in artifact.items():
    if any(token in key for token in ('bootstrap','start','observer','trace','handoff')):
        print(key,json.dumps(value,ensure_ascii=False)[:15000])
with np.load(run/'trace.npz',allow_pickle=False) as arrays:
    print('TRACE_KEYS',arrays.files)
    for key in arrays.files:
        if any(token in key for token in ('time','state','stage','phase','q_ref')):
            print(key,arrays[key].shape,arrays[key][:3].tolist())
result=json.loads((run.parent/'rollout_result.json').read_text())
case=json.loads((ROOT/result['case_path']).read_text())
print('TASK_SPEC',case['task'])
old=read_json(RAW/'runs/pilot_scratch_v1_rep_01/rep_01/runtime_artifacts.json')
print('OLD_TERMINAL_TRACE',json.dumps(old['trace'][-1],ensure_ascii=False)[:6000])
for key in ('execution_attempts','last_boundary','wall_physics'):
    print('NEW_'+key,json.dumps(artifact[key],ensure_ascii=False)[:10000])
