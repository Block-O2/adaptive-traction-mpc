"""Opt-in capture of already produced deployable planner bytes for profiling.

Call capture_payload(payload, arguments) AFTER snapshot_research_task_call has
made its unchanged payload. Extra disk IO is outside timing qualification.
No runtime/plant object is accepted. Never load external untrusted pickles.
"""
import hashlib
import json
import os
from pathlib import Path


def capture_payload(payload, arguments):
    destination=os.environ.get('VALUE_LATENCY_SNAPSHOT_DIR')
    if not destination:return
    phase=getattr(arguments.get('phase'),'value',str(arguments.get('phase')))
    if phase not in ('OUTBOUND','RETURN'):return
    root=Path(destination)
    root.mkdir(parents=True,exist_ok=True)
    path=root/(phase.lower()+'.pickle')
    # Preserve first request per phase and never overwrite captured evidence.
    if path.exists():return
    with path.open('xb') as stream:stream.write(payload)
    (root/(phase.lower()+'.json')).write_text(json.dumps(dict(
        schema='learning_latency_deployable_snapshot_v1',phase=phase,
        sha256=hashlib.sha256(payload).hexdigest(),size_bytes=len(payload),
        source='unchanged research snapshot bytes, before worker submission',
        truth_in_controller=False,
        warning='capture IO adds overhead; run is not a frozen runtime benchmark'),indent=2)+'\n')
