"""Offline complete/partial evidence bookkeeping and applied receipt modes.

PASS here means retained evidence/accounting is internally consistent. It never
promotes an incomplete run, unqualified physics, or partial integral to a result.
"""
from pathlib import Path
import importlib.util
import json
import hashlib
import collections
import sys
import time
import numpy as np

sys.dont_write_bytecode=True
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_cross_patient_b_h150_v1')
spec=importlib.util.spec_from_file_location('raw_read_only',P/'control/independent_recompute.py')
raw=importlib.util.module_from_spec(spec);spec.loader.exec_module(raw)
def read(path,default=None):return json.loads(Path(path).read_text()) if Path(path).exists() else default
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()
def put(name,data):
    for root in [P,Path(read(P/'ENVIRONMENT.json')['review'])]:
        path=root/name
        assert not path.exists(),'PRESERVE_PRIOR_AUDIT'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
def review(patient):
    owner=read(P/'audit'/(patient+'_OWNER.json'),{})
    done=read(P/(patient+'_DONE.json'),{})
    exit_rec=read(P/(patient+'_WORKER_EXIT.json'),{})
    if not owner.get('joined'):return dict(patient_id=patient,status='WAITING_JOIN')
    if not done or not exit_rec:return dict(patient_id=patient,status='MISSING_FINALIZATION_EVIDENCE',owner=owner)
    assert done.get('all_children_joined') and exit_rec.get('active_child') is None
    output='audit/'+patient+'_FAILURE_PRESERVATION_AUDIT.json'
    if (P/output).exists():return read(P/output)
    attempts=[json.loads(line) for line in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
    rows=[];checks={};is_partial=False
    for arm in ['B','H150','parent']:
        ident=patient+'_'+arm;folder=P/'source/results'/ident
        starts=[x for x in attempts if x['event']=='START' and x['id']==ident]
        ends=[x for x in attempts if x['event']=='END' and x['id']==ident]
        ev=read(P/'reports'/(ident+'_CROSS_EVALUATION.json'),{})
        su=read(folder/'summary.json',{})
        files=[p for p in [folder/'summary.json',folder/'trace.npz',folder/'runtime_artifacts.json.gz',folder/'HIGH_ROM_CASE_RESULT.json',P/'reports'/(ident+'_ERROR.json'),P/'learning'/(ident+'_PARTIAL_STATE_ACTION.json'),P/'output'/(ident+'_PARTIAL_COMPUTE.json')] if p.exists()]
        partial=not ev.get('complete_task') or ev.get('integration')!='PASS'
        is_partial=is_partial or partial
        state='NOT_STARTED' if not starts else 'PARTIAL_OR_UNVERIFIED_PRESERVED' if partial else 'COMPLETE_REPORTED_RESULT'
        row=dict(id=ident,state=state,start_count=len(starts),end_count=len(ends),source_hashes={str(p):sha(p) for p in files},
                 reported_complete=ev.get('complete_task'),reported_axes=ev.get('axes'),reported_full_J_F_N_s=ev.get('J_F_N_s'),
                 error=read(P/'reports'/(ident+'_ERROR.json')),summary_status=su.get('status'),summary_abort_reason=su.get('abort_reason'))
        checks[ident+'_start_end_closure']=len(starts)==len(ends) and len(starts)<=1 and all(x.get('joined') is True for x in ends)
        checks[ident+'_no_partial_full_integral']=not partial or ev.get('J_F_N_s') is None
        checks[ident+'_no_partial_qualified_pass']=not partial or (ev.get('qualification')!='COMPLETE_QUALIFIED_PASS' and ev.get('absolute_task_execution_qualified') is not True)
        if not starts:
            checks[ident+'_not_started_no_fabricated_result']=not ev and not su
        if partial and (folder/'trace.npz').exists():
            try:
                with np.load(folder/'trace.npz') as z:
                    mask=z['stage']=='TASK';t=z['time_s'][mask];f=np.linalg.norm(z['physical_cuff_force_world_n'][mask],axis=1)
                    row['prefix_arithmetic']=dict(task_rows=len(t),duration_s=float(t[-1]-t[0]) if len(t)>1 else None,
                        observed_prefix_J_F_N_s=float(f[:-1]@np.diff(t)) if len(t)>1 else None,
                        full_task_result=False,extrapolated=False)
            except Exception as error:row['prefix_read_error']=str(error)
        artifact=folder/'runtime_artifacts.json.gz'
        receipt_path='audit/'+ident+'_RECEIPT_MODE_EVIDENCE.json'
        if artifact.exists() and not (P/receipt_path).exists():
            before=sha(artifact);applied=collections.Counter();unapplied=collections.Counter();native=collections.Counter();positive=collections.Counter();events=collections.Counter()
            try:
                n=0
                for r in raw.array_items(artifact,'command_receipts'):
                    n+=1;mode=str(r.get('mode'))
                    if r.get('applied') is True:
                        applied[mode]+=1;native[mode]+=r.get('native_steps',0)
                        if r.get('native_steps',0)>0:positive[mode]+=1
                    else:unapplied[mode]+=1
                for r in raw.array_items(artifact,'safe_fallback_events'):events[str(r.get('event'))]+=1
                receipt=dict(id=ident,status='RAW_RECEIPT_CLASSIFICATION',receipt_count=n,
                    applied_mode_counts=dict(applied),unapplied_mode_counts=dict(unapplied),
                    applied_positive_step_mode_counts=dict(positive),applied_native_steps_by_mode=dict(native),
                    fallback_event_type_counts=dict(events),original_sha256=before,
                    original_bytes_unchanged=sha(artifact)==before,
                    caveat='ESCAPE_ADMITTED is certification/admission; executed fallback requires applied positive-step command or explicit commit event. Receipt classification does not independently establish ownership.',new_physics_starts=0)
                assert receipt['original_bytes_unchanged'];put(receipt_path,receipt)
            except Exception as error:row['receipt_inventory_error']=str(error)
        row['receipt_evidence']=receipt_path if (P/receipt_path).exists() else None
        rows.append(row)
    paired=read(P/'reports'/(patient+'_PAIR_ANALYSIS.json'))
    if paired and not paired.get('full_integral_comparison_valid'):
        checks['no_partial_pair_gain']=all(paired.get(k) is None for k in ['gain_fraction','gain_percent','gain_N_s'])
        checks['no_partial_pair_qualification']=paired.get('complete_qualified_H150') is not True and paired.get('relative_gain_is_qualified') is not True
    result=dict(patient_id=patient,status='EVIDENCE_PRESERVATION_PASS' if all(checks.values()) else 'EVIDENCE_PRESERVATION_FAIL',
                has_partial_or_unrun_arm=is_partial,checks=checks,rows=rows,
                done_status=done['status'],cold_commissioning_reached=done.get('cold_commissioning_reached'),
                scientific_promotion=False,full_raw_verification='Separate INDEPENDENT_COMPLETE patient audit; this audit never substitutes for it',
                unix=time.time(),new_physics_starts=0)
    assert not any(x in sys.modules for x in ['mujoco','cross_runner','study_common','sac_env'])
    put(output,result);return result

if __name__=='__main__':
    rows=[review(pid) for pid in sys.argv[1:] or read(P/'VIRTUAL_PATIENT_COHORT.json')['order']]
    print(json.dumps([dict(patient_id=r['patient_id'],status=r['status'],has_partial=r.get('has_partial_or_unrun_arm')) for r in rows]))
