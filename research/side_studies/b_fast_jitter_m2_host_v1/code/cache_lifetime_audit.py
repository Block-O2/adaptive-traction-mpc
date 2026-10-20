"""Recorded exact-byte certificate ownership and same-boundary nominal scopes."""
from task_bootstrap import *
from analyze_timing import header_requests
from collections import Counter
def main():
 rows=[];issues=[];reason_counts=Counter();start=time.time()
 for p in sorted((STUDY/'output').glob('*_CACHE_EVIDENCE.json')):
  id=p.name.removesuffix('_CACHE_EVIDENCE.json');events=json.loads(p.read_text())['rows'];artifact=STUDY/'source/results'/id/'runtime_artifacts.json.gz';requests={r['request_id']:r for r in header_requests(artifact)};local=[]
  for event in events:
   q=requests.get(event['owner']);errors=[]
   if q is None or q['sensor_capture_ns']!=event['source_capture_ns']:errors.append('CACHE_REQUEST_SOURCE_MISMATCH')
   if event['released_ns']<event['created_ns']:errors.append('NEGATIVE_BOUNDARY_LIFETIME')
   if event['hits']<0 or event['misses']<0:errors.append('NEGATIVE_COUNTER')
   if len(event['input_sha256'])!=64:errors.append('INPUT_SHA_FORMAT')
   if errors:issues.append(dict(id=id,owner=event['owner'],issues=errors))
   local.append(dict(owner=event['owner'],source_capture_ns=event['source_capture_ns'],input_sha256=event['input_sha256'],hits=event['hits'],misses=event['misses'],scope_ms=(event['released_ns']-event['created_ns'])/1e6))
  rows.append(dict(id=id,kind='SAME_BOUNDARY_NOMINAL',artifact_sha256=sha(artifact),evidence_sha256=sha(p),events=local))
 for p in sorted((STUDY/'output').glob('*_CERTIFICATE_REUSE.json')):
  id=p.name.removesuffix('_CERTIFICATE_REUSE.json');events=json.loads(p.read_text())['rows'];artifact=STUDY/'source/results'/id/'runtime_artifacts.json.gz';requests={r['request_id']:r for r in header_requests(artifact)};local=[]
  for event in events:
   reason_counts[event['reason']]+=1;errors=[];q=requests.get(event['request_id']);hit=event['decision_reused'];age=None if event['source_capture_ns'] is None else (event['checked_ns']-event['source_capture_ns'])/1e6
   if hit:
    if q is None or q['sensor_capture_ns']!=event['source_capture_ns']:errors.append('REUSE_REQUEST_SOURCE_MISMATCH')
    if event['payload_sha256'] not in event['certificate_payload_hashes']:errors.append('EXACT_BYTES_NOT_CERTIFIED')
    if age is None or not 0<=age<100:errors.append('ORIGINAL_GENERIC_EXPIRY_VIOLATION')
    if event['reason']!='EXACT_SNAPSHOT_SAME_REQUEST_HIT':errors.append('UNSUPPORTED_REUSE_REASON')
   if not event['native_safe_fallback_prepare_retained'] or not event['current_model_activation_revalidation_retained']:errors.append('MANDATORY_EXECUTION_CHECK_NOT_RETAINED')
   if errors:issues.append(dict(id=id,request_id=event['request_id'],issues=errors))
   local.append(dict(request_id=event['request_id'],source_capture_ns=event['source_capture_ns'],decision_reused=hit,reason=event['reason'],age_at_reuse_ms=age,payload_sha256=event['payload_sha256']))
  rows.append(dict(id=id,kind='EXACT_BYTE_REQUEST_CERTIFICATE',artifact_sha256=sha(artifact),evidence_sha256=sha(p),events=local))
 sources={name:sha(STUDY/'code'/name) for name in ('shared_nominal.py','certified_snapshot.py','certified_snapshot_v2.py','async_native_worker.py')}
 out=dict(status='PASS_RECORDED_OWNERSHIP_AND_SOURCE_SCOPE' if not issues else 'FAIL',rows=rows,issues=issues,source_hashes=sources,nominal_boundary_events=sum(len(r['events']) for r in rows if r['kind']=='SAME_BOUNDARY_NOMINAL'),certificate_events=sum(len(r['events']) for r in rows if r['kind']=='EXACT_BYTE_REQUEST_CERTIFICATE'),certificate_reason_counts=dict(reason_counts),physics_added=0,wall_seconds=time.time()-start,limitation='Recorded parent/thread events are checked directly against original request/source metadata. E5/E6/E7 worker-local certificate dictionary is cleared at each execute boundary by source contract; disabled full profiling is not inferred to provide an event-by-event runtime cache attestation. Scientific full-native gates separately validate the executed trajectory. Generic expiry eligibility is not strict realtime qualification.')
 save(STUDY/'reports/CACHE_LIFETIME_AUDIT.json',out);print(json.dumps({k:v for k,v in out.items() if k not in ('rows','source_hashes')}));assert not issues
if __name__=='__main__':main()
