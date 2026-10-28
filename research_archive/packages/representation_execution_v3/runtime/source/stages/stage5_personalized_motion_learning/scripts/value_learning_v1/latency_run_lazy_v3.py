"""One sequential v3 development rollout with established immediate archival."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import numpy as np
from research_campaign import D,RAW,RUNS,launch,save,C

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--kind',choices=('capture','clean'),required=True)
    args=parser.parse_args()
    if datetime.now(timezone.utc)>=datetime.fromisoformat(C['hard_deadline_utc']):raise RuntimeError('campaign hard deadline')
    freeze=D/'LATENCY_LAZY_COMPARATOR_REVISION_V3.json'
    frozen=json.loads(freeze.read_text())
    adapter=Path(__file__).with_name('research_adapter.py')
    key=str(adapter.relative_to(Path(__file__).resolve().parents[4]))
    if hashlib.sha256(adapter.read_bytes()).hexdigest()!=frozen['source_original_content_sha256'][key]:raise ValueError('v3 frozen adapter changed before run')
    spec=json.loads((RAW/'specs/latency_clean_subset0236_legacy1_v1.json').read_text())
    spec.update(lazy_legacy_comparator_on_committed=True,proposal_bank_source_indices=[0,2,3,6],
                model_version='OFFLINE_LAZY_COMPARATOR_V3_'+args.kind.upper())
    spec.pop('capture_snapshot_dir',None)
    run_id='latency_lazy_v3_'+args.kind
    if args.kind=='capture':spec['capture_snapshot_dir']=str(RAW/'latency_lazy_snapshots_v3')
    result=launch({'condition':'sync_120','run_id':run_id,'spec':spec})
    old=json.loads((RUNS/'latency_clean_subset0236_legacy1_v1/rollout_result.json').read_text())
    check={'old_run_id':old['run_id'],'old_J_F_task_n_s':old['J_F_task_n_s'],
           'new_J_F_task_n_s':result.get('J_F_task_n_s'),'new_status':result['status'],
           'J_F_abs_error_n_s':abs(result['J_F_task_n_s']-old['J_F_task_n_s']) if result.get('J_F_task_n_s') is not None else None}
    if result['status']=='VALID':
        with np.load(RUNS/old['run_id']/'rep_01/trace.npz',allow_pickle=False) as a,np.load(RUNS/run_id/'rep_01/trace.npz',allow_pickle=False) as b:
            for key in ('evaluation_only_human_state_rad_rad_s','physical_cuff_force_world_n'):
                x=a[key][a['stage']=='TASK'];y=b[key][b['stage']=='TASK']
                check[key+'_max_error']=float(np.max(np.abs(x-y))) if x.shape==y.shape else None
        check['same_observed_J_and_trace']=bool(check['J_F_abs_error_n_s']<1e-9 and all(check.get(key+'_max_error')==0. for key in ('evaluation_only_human_state_rad_rad_s','physical_cuff_force_world_n')))
    save(RAW/('latency_lazy_v3_'+args.kind+'_provenance.json'),{
        'schema':'bounded_lazy_comparator_v3_actual_run','run_id':run_id,'kind':args.kind,
        'freeze_original_content_sha256':hashlib.sha256(freeze.read_bytes()).hexdigest(),
        'actual_model_sha256':result.get('model_sha256_at_start'),'extra_capture_io':args.kind=='capture',
        'model_immutable':result.get('active_model_file_immutable_during_rep'),'eager_v2_equivalence':check,
        'hardware_realtime_qualified':False,'not_a_new_policy_or_test_retuning':True})
    print(json.dumps(check),flush=True)
