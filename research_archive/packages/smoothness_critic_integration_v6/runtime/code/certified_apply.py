"""B5: ensure actual submitted carry/prefix/terminal snapshot has a certificate."""
import pickle,hashlib,time
EVENTS=[]
def ensure(module,b):
 slot=getattr(module.LOCAL,'build',None);req=b['request'];assert slot is not None and slot['owner']==req.request_id and slot['source_capture_ns']==req.sensor_capture_ns
 payload=module.snapshot_task_call(b['adaptive_planner'],b['arguments']);key=hashlib.sha256(payload).hexdigest();already=key in slot['certificates'];t=time.monotonic_ns()
 if not already:
  clone,args=pickle.loads(payload);decision=clone.decide(**args);slot['certificates'][key]=pickle.dumps((clone,decision),protocol=5)
 EVENTS.append(dict(request_id=req.request_id,source_capture_ns=req.sensor_capture_ns,submitted_payload_sha256=key,already_certified=already,extra_full_native_decide=not already,elapsed_ms=(time.monotonic_ns()-t)/1e6,scope='actual unchanged submitted spec including late carry/prefix/terminal, same boundary only',native_safety_prepare_and_activation_revalidation_retained=True))
