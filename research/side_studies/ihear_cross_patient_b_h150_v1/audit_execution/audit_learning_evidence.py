"""Read only, completed-run schema/evidence inventory. No runner/physics imports."""
from pathlib import Path
import importlib.util
import json
import sys
import hashlib
import collections
import os
import time
import numpy as np

sys.dont_write_bytecode = True
P = Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
spec = importlib.util.spec_from_file_location('raw_arithmetic_only', P/'control/independent_recompute.py')
raw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw)

def read(path): return json.loads(Path(path).read_text())
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''): h.update(block)
    return h.hexdigest()
def clean(x):
    if isinstance(x, dict): return {k:clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [clean(v) for v in x]
    if isinstance(x, np.ndarray): return x.tolist()
    if isinstance(x, np.generic): return x.item()
    return x
def put(rel, obj):
    for root in [P,Path(read(P/'ENVIRONMENT.json')['review'])]:
        dest = root/rel
        assert not dest.exists(), 'PRESERVE_EXISTING:'+str(dest)
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(clean(obj),indent=2,allow_nan=False)+'\n')
def paths(row, prefix=''):
    if not isinstance(row,dict): return [prefix]
    out=[]
    for k,v in row.items():
        p=prefix+'.'+k if prefix else k
        if isinstance(v,dict):out.extend(paths(v,p))
        else:out.append(p+('[]' if isinstance(v,list) else ''))
    return out

def run(ident):
    if (P/'audit'/(ident+'_LEARNING_EXECUTION_EVIDENCE.json')).exists():
        old=read(P/'audit'/(ident+'_LEARNING_EXECUTION_EVIDENCE.json'))
        return dict(id=ident,status='PARTIAL_EVIDENCE_INVENTORIED' if old.get('complete_task') is False else 'COMPLETE_EVIDENCE_INVENTORIED',already_exists=True)
    patient=ident.split('_')[0]
    assert read(P/(patient+'_DONE.json'))['all_children_joined']
    assert read(P/'audit'/(patient+'_OWNER.json'))['joined']
    assert read(P/(patient+'_WORKER_EXIT.json'))['active_child'] is None
    folder=P/'source/results'/ident
    su=read(folder/'summary.json'); compact=read(P/'learning'/(ident+'_STATE_ACTION.json'))
    label_file=P/'output'/(ident+'_DECISIONS.json')
    if not label_file.exists(): label_file=P/(ident+'_DECISIONS.json')
    labels=read(label_file)['rows']
    sources=[folder/'summary.json',folder/'trace.npz',folder/'runtime_artifacts.json.gz',P/'learning'/(ident+'_STATE_ACTION.json'),label_file]
    before={str(p):sha(p) for p in sources}
    inventory={}
    for key in ['requests','execution_attempts','activation_validations','reference_governor_records','future_handoff_bridges','rolling_splice_events','safe_fallback_events','causal_tracking_request_snapshots','command_receipts']:
        rows=[];count=0;fields=set();categories=collections.defaultdict(collections.Counter)
        try:
            for r in raw.array_items(folder/'runtime_artifacts.json.gz',key):
                count+=1;fields.update(paths(r))
                if len(rows)<2:rows.append(r)
                for k,v in r.items():
                    if isinstance(v,(str,bool)) or v is None:categories[k][str(v)]+=1
            inventory[key]=dict(present=True,count=count,fields=sorted(fields),first_two=rows,categories=dict(categories))
        except ValueError as e: inventory[key]=dict(present=False,error=str(e))
    with np.load(folder/'trace.npz') as z:
        fields={k:dict(shape=z[k].shape,dtype=str(z[k].dtype)) for k in z.files}
        task=z['stage']=='TASK';ts=z['time_s'];rows=[]
        for row in compact['causal_rows']:
            i=int(np.argmin(abs(ts-row['physical_s']))); exact=abs(ts[i]-row['physical_s'])<1e-8
            obs=np.array(row['estimated_q_dq']);ref=np.array(row['reference_q_dq'])
            emitted=np.r_[z['reference_q_rad'][i],z['reference_dq_rad_s'][i]]
            est=z['estimated_human_state_rad_rad_s'][i]
            rows.append(dict(request_id=row['request_id'],physical_s=row['physical_s'],trace_index=i,time_match=exact,
                             original_estimated_q_dq_rad_rad_s=obs,original_request_reference_q_dq_rad_rad_s=ref,
                             original_request_tracking_q_dq_rad_rad_s=row['tracking_q_dq'],
                             original_error_arithmetic_max=float(np.max(abs(obs-ref-np.array(row['tracking_q_dq'])))),
                             trace_estimated_q_dq_rad_rad_s=est,trace_emitted_reference_q_dq_rad_rad_s=emitted,
                             trace_sample_aligned_causal_tracking_q_dq_rad_rad_s=est-emitted,
                             compact_vs_trace_observer_max=float(np.max(abs(obs-est))),
                             request_vs_emitted_reference_max=float(np.max(abs(ref-emitted)))))
        first_legacy=labels[0]; scales=np.r_[np.radians([125.,125.,45.,75.]),np.radians([125.,125.,45.,75.])]
        normalized=np.asarray(first_legacy['observation'])[:8]
        tq=z['cr12_actuator_command_nm'][task]
        torque=dict(peak_abs_actuator_nm=np.max(abs(tq),axis=0),reported_peak_fraction=su['task'].get('peak_robot_torque_fraction'))
        trace_fields=fields
    schema=dict(id=ident,complete_task=su['status']=='COMPLETE',summary_status=su['status'],full_task_metrics_inferred=False,units=['rad','rad','rad/s','rad/s'],order=['hip_q','knee_q','hip_dq','knee_dq'],
                compact_observation_is_normalized=False,
                compact_reference_semantics='Planner request reference; may be future handoff endpoint. Do not label as always the emitted reference at the observation timestamp.',
                legacy_observation_is_normalized=True,legacy_dtype='float32',legacy_first8_scales=scales,
                first_legacy_normalized=normalized,first_legacy_first8_decoded_rad_rad_s=normalized*scales,
                first_legacy_task_s=first_legacy.get('task_s'),first_legacy_phase=first_legacy.get('phase'),
                compact_count=len(compact['causal_rows']),legacy_count=len(labels),summary_decision_count=len(su['decisions']),
                omitted_prefix_note='Fork children reset compact online_records after shared prefix; original full summary/legacy decisions and parent retain shared prefix.',
                derived_rows=rows,source_hashes=before,truth_used_in_derived_learning_fields=False,
                original_bytes_unchanged=all(sha(p)==h for p,h in before.items()))
    audit=dict(id=ident,complete_task=su['status']=='COMPLETE',summary_status=su['status'],full_task_metrics_inferred=False,source_hashes=before,runtime_arrays=inventory,trace_fields=trace_fields,
               summary_decision_fields=paths(su['decisions'][0]) if su['decisions'] else [],
               summary_learning_record_fields=paths(su['learning_records'][0]) if su['learning_records'] else [],
               summary_qualification=su.get('qualification'),summary_task=su['task'],robot_torque=torque,
               compact_fallback_source_gap=dict(summary_has_fallback_events='fallback_events' in su,
                 compact_evaluation_fallbacks_source='summary.get(fallback_events,[]) is not authoritative; use runtime.safe_fallback_events'),
               original_bytes_unchanged=all(sha(p)==h for p,h in before.items()),new_physics_starts=0)
    assert not any(k in sys.modules for k in ['mujoco','study_common','cross_runner','sac_env'])
    assert schema['original_bytes_unchanged'] and audit['original_bytes_unchanged']
    put('derived/'+ident+'_CAUSAL_SCHEMA_VERIFICATION.json',schema)
    put('audit/'+ident+'_LEARNING_EXECUTION_EVIDENCE.json',audit)
    print(json.dumps(dict(id=ident,counts={k:v.get('count') for k,v in inventory.items()},compact_count=len(rows),
                         time_matches=all(r['time_match'] for r in rows),max_observer_difference=max((r['compact_vs_trace_observer_max'] for r in rows),default=None),
                         max_request_reference_difference=max((r['request_vs_emitted_reference_max'] for r in rows),default=None),
                         normalized_first8=normalized.tolist(),decoded_first8=(normalized*scales).tolist())),flush=True)
    return dict(id=ident,status='COMPLETE_EVIDENCE_INVENTORIED' if su['status']=='COMPLETE' else 'PARTIAL_EVIDENCE_INVENTORIED')

def completed_inventory():
    results=[]
    for patient in read(P/'VIRTUAL_PATIENT_COHORT.json')['order']:
        done=P/(patient+'_DONE.json');owner=P/'audit'/(patient+'_OWNER.json');exited=P/(patient+'_WORKER_EXIT.json')
        if not done.exists() or not owner.exists() or not exited.exists():continue
        if not read(done).get('all_children_joined') or not read(owner).get('joined') or read(exited).get('active_child') is not None:continue
        for arm in ['B','H150','parent']:
            ident=patient+'_'+arm
            required=[P/'source/results'/ident/'summary.json',P/'source/results'/ident/'trace.npz',P/'source/results'/ident/'runtime_artifacts.json.gz',P/'learning'/(ident+'_STATE_ACTION.json'),P/'output'/(ident+'_DECISIONS.json')]
            missing=[str(p.relative_to(P)) for p in required if not p.exists()]
            if missing:
                results.append(dict(id=ident,status='MISSING_OR_PARTIAL_PRESERVED',missing=missing));continue
            try:results.append(run(ident))
            except Exception as e:results.append(dict(id=ident,status='INVENTORY_ERROR_PRESERVED',error=str(e)))
    return results

def combined(results):
    rows=[]
    for result in results:
        ident=result['id'];entry=dict(result)
        schema_path=P/'derived'/(ident+'_CAUSAL_SCHEMA_VERIFICATION.json');evidence_path=P/'audit'/(ident+'_LEARNING_EXECUTION_EVIDENCE.json')
        if schema_path.exists() and evidence_path.exists():
            sc=read(schema_path);ev=read(evidence_path);ars=ev['runtime_arrays']
            entry.update(evidence_path=str(evidence_path.relative_to(P)),schema_path=str(schema_path.relative_to(P)),
               complete_task=sc.get('complete_task',True),summary_status=sc.get('summary_status','COMPLETE'),
               source_bytes_unchanged=sc['original_bytes_unchanged'] and ev['original_bytes_unchanged'],
               compact_rows=sc['compact_count'],legacy_rows=sc['legacy_count'],summary_decisions=sc['summary_decision_count'],
               observer_units=sc['units'],compact_observation_normalized=False,legacy_observation_normalized=True,
               all_compact_observations_equal_trace=all(r['time_match'] and r['compact_vs_trace_observer_max']==0 for r in sc['derived_rows']),
               request_reference_vs_emitted_max=max([r['request_vs_emitted_reference_max'] for r in sc['derived_rows']],default=None),
               raw_fallback_events=ars['safe_fallback_events'].get('categories'),raw_command_modes=ars['command_receipts'].get('categories',{}).get('mode'),
               request_outcomes=ars['requests'].get('categories',{}).get('outcome'),splice_outcomes=ars['rolling_splice_events'].get('categories',{}).get('outcome'),
               runtime_array_counts={k:v.get('count') for k,v in ars.items()},robot_torque=ev['robot_torque'],
               compact_fallbacks_is_authoritative=False)
        rows.append(entry)
    put('audit/LEARNING_EXECUTION_FIELD_AUDIT.json',dict(scope='Offline field preservation and schema audit; never scientific promotion',
         rows=rows,new_physics_starts=0,controller_or_physics_imports=False,
         final_request_reference_rule='Original compact tracking uses planner request reference; sample-aligned emitted-reference tracking is separately derived from causal trace fields.',
         final_fallback_rule='Use runtime.safe_fallback_events event types and command receipt modes. ESCAPE_ADMITTED is a certificate/admission event, not proof of executed escape.',
         includes_preserved_partial_evidence=any(r.get('complete_task') is False for r in rows),partial_runs_not_promoted=True))

if __name__=='__main__':
    if '--watch' in sys.argv[1:]:
        print('OFFLINE_LEARNING_AUDITOR_STARTED',os.getpid(),flush=True)
        reported=set();results=[]
        while time.time()<read(P/'RUN_PLAN.json')['hard_stop_unix']:
            results=completed_inventory()
            for row in results:
                key=(row['id'],row['status'])
                if key not in reported:print('LEARNING_AUDIT',*key,flush=True);reported.add(key)
            ended=(P/'SERIAL_CAMPAIGN_DONE.json').exists() or (P/'PHYSICS_STOP.json').exists()
            active=read(P/'OWNED_ACTIVE_PROCESS.json') if (P/'OWNED_ACTIVE_PROCESS.json').exists() else {}
            if ended and active.get('status')=='IDLE':break
            time.sleep(30)
        combined(results)
        print('OFFLINE_LEARNING_AUDITOR_STOPPED',os.getpid(),flush=True)
    elif '--completed' in sys.argv[1:]:
        print(json.dumps(completed_inventory()),flush=True)
    else:
        for ident in sys.argv[1:] or ['P00_H150']:run(ident)
