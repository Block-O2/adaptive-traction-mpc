import hashlib
import json
import sys
from pathlib import Path
ROOT=Path('/home/hank/coding/adaptive-traction-mpc-learning')
STAGE=ROOT/'stages/stage5_personalized_motion_learning'
SCRIPTS=STAGE/'scripts/value_learning_v1'
sys.path.insert(0,str(SCRIPTS))
from evidence_io import read_json
from latency_report_section import render_section
RAW=STAGE/'results/value_learning_research_v1'
D=STAGE/'docs/value_learning_research_v1'

def main():
    section=render_section(read_json(RAW/'latency_host_profiles_v3/CLEAN_LAZY_HOST_PROFILE.json'),
        read_json(RAW/'latency_cpu_models_scientific_v1/CPU_MODEL_LATENCY.json'),
        gate=read_json(D/'ONLINE_LATENCY_PROMOTION_GATE.json'),
        updates=read_json(D/'TRAINING_UPDATE_LATENCY.json'),
        pilot=read_json(D/'ONLINE_POLICY_IMPROVEMENT_PILOT.json'),
        lifecycle=read_json(D/'LATENCY_PILOT_UPDATE_LIFECYCLE_AUDIT.json'),
        protocol=read_json(D/'PILOT_PROTOCOL_DEVIATIONS.json'),
        capture_profile=read_json(RAW/'latency_host_profiles_v1/CAPTURE_HOST_PROFILE.json'),
        scaling=[read_json(RAW/name) for name in (
            'latency_replay_v1/OUTBOUND_SELECTED_RIDGE.json',
            'latency_replay_v1/RETURN_SELECTED_RIDGE.json',
            'latency_replay_v1/OUTBOUND_SUBSET_0239_SELECTED_RIDGE.json',
            'latency_replay_v1/OUTBOUND_SUBSET_0236_SELECTED_RIDGE.json',
            'latency_replay_v1/MOVING_OUTBOUND_SELECTED_RIDGE.json',
            'latency_replay_v3/OUTBOUND_SUBSET_0236_LAZY_RIDGE.json',
            'latency_replay_v3/MOVING_OUTBOUND_LAZY_RIDGE.json')])
    (D/'LATENCY_REPORT_SECTION.md').write_text(section,encoding='utf-8')
    audit=read_json(D/'LATENCY_PILOT_UPDATE_LIFECYCLE_AUDIT.json')
    print('Final reports generated',D/'LATENCY_REPORT_SECTION.md')
    for s in audit['sessions']:
        print(s['mode'],'fresh boundary exact comparisons',[
            (v['repetition'],v['exact_same_fresh_native_initial_arrays_as_first'])
            for v in s['fresh_native_initial_boundary_comparisons']])
        print('model lifecycle',json.dumps(s['model_lifecycle'],ensure_ascii=False)[:4500])
    for p in ('LATENCY_REPORT_SECTION.md','LATENCY_BOUNDARY_CONTINUITY_AUDIT.json',
              'LATENCY_PILOT_UPDATE_LIFECYCLE_AUDIT.json'):
        print(p,hashlib.sha256((D/p).read_bytes()).hexdigest())

if __name__=='__main__':main()
