"""Opt-in capture of already produced deployable planner bytes for profiling.

Call capture_payload(payload, arguments) AFTER snapshot_research_task_call has
made its unchanged payload. Extra disk IO is outside timing qualification.
No runtime/plant object is accepted. Never load external untrusted pickles.
"""
import hashlib
import json
import os
import pickle
from pathlib import Path


def capture_payload(payload, arguments):
    destination=os.environ.get('VALUE_LATENCY_SNAPSHOT_DIR')
    if not destination:return
    phase=getattr(arguments.get('phase'),'value',str(arguments.get('phase')))
    if phase not in ('OUTBOUND','RETURN'):return
    root=Path(destination)
    root.mkdir(parents=True,exist_ok=True)
    reference=arguments.get('current_reference_state',())
    velocity=[float(value) for value in reference[2:]]
    stationary=not any(abs(value)>1e-12 for value in velocity)
    # Inspect only the already serialized deployable research snapshot. This
    # extra opt-in unpickle/IO cost is explicitly outside normal profiling.
    adaptive,_=pickle.loads(payload)
    planner=adaptive.planner
    path_index=getattr(planner,'research_phase_index',None)
    spec=planner.research_spec
    committed=bool(spec.get('committed_descriptor'))
    stem='moving_outbound' if (phase=='OUTBOUND' and path_index is not None
             and path_index>=1 and committed and not stationary) else phase.lower()
    path=root/(stem+'.pickle')
    # Preserve first request per phase and never overwrite captured evidence.
    if path.exists():return
    with path.open('xb') as stream:stream.write(payload)
    with (root/(stem+'.json')).open('x',encoding='utf-8') as metadata:
        metadata.write(json.dumps(dict(
        schema='learning_latency_deployable_snapshot_v1',phase=phase,
        path_index=path_index,continuation_committed=committed,
        reference_velocity_rad_s=velocity,reference_stationary=stationary,
        captured_role='actual_moving_committed_outbound' if stem=='moving_outbound' else 'first_phase_request',
        lazy_legacy_comparator_on_committed=bool(spec.get('lazy_legacy_comparator_on_committed',False)),
        proposal_bank_source_indices=spec.get('proposal_bank_source_indices'),
        proposal_descriptor_content_sha256=hashlib.sha256(json.dumps(spec.get('proposal_descriptors',[]),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest(),
        sha256=hashlib.sha256(payload).hexdigest(),size_bytes=len(payload),
        source='unchanged research snapshot bytes, before worker submission',
        truth_in_controller=False,
        warning='capture unpickle and IO add overhead; run is not a frozen runtime benchmark'),indent=2)+'\n')
