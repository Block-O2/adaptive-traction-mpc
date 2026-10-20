"""Diagnostic-only capture of ORIGINAL activation inputs, with paid host cost."""
from extension_common import *
import pickle,functools,traceback,threading
CAPTURES=[]

def install():
    import study_common
    from traction_mpc_stage5.full3d_adaptive_integration_v1 import activation_validation as av
    for name in ('validate_activation','validate_rolling_composite'):
        original=getattr(av,name)
        def factory(original,name):
            @functools.wraps(original)
            def wrapper(*args,**kwargs):
                enter=time.monotonic_ns();payload=None;capture_error=None
                try:payload=pickle.dumps((args,kwargs),protocol=5)
                except Exception as e:capture_error=type(e).__name__+':'+str(e)
                captured=time.monotonic_ns();result=None;error=None
                try:
                    result=original(*args,**kwargs);return result
                except BaseException as e:
                    error=type(e).__name__+':'+str(e);raise
                finally:
                    finish=time.monotonic_ns()
                    CAPTURES.append(dict(name=name,enter_ns=enter,capture_finish_ns=captured,original_finish_ns=finish,payload=payload,capture_error=capture_error,original_error=error,result=result,thread=threading.get_ident(),phase=getattr(kwargs.get('phase'),'value',None)))
            return wrapper
        setattr(av,name,factory(original,name))

def main():
    install()
    import worker
    try:worker.main()
    finally:
        target=EXT/'ACTIVATION_INPUTS';target.mkdir(exist_ok=True);manifest=[]
        for i,row in enumerate(CAPTURES):
            p=target/f'{i:03d}.pkl';p.write_bytes(pickle.dumps(row,protocol=5))
            manifest.append(dict(index=i,path=str(p),sha256=sha(p),name=row['name'],phase=row['phase'],enter_ns=row['enter_ns'],capture_finish_ns=row['capture_finish_ns'],original_finish_ns=row['original_finish_ns'],capture_error=row['capture_error'],original_error=row['original_error'],capture_ms=(row['capture_finish_ns']-row['enter_ns'])/1e6,original_with_nested_capture_ms=(row['original_finish_ns']-row['capture_finish_ns'])/1e6))
        save(EXT/'ACTIVATION_INPUT_MANIFEST.json',dict(status='CAPTURED_DIAGNOSTIC_WITH_PAID_OVERHEAD',rows=manifest,saved_after_worker=True,physics_attempts=1,Q_updates=0,no_controller_decision_replacement=True,no_timestamp_reset=True,overhead_not_subtracted_from_actual_age=True,qualification_claim=False,limitation='Instrumentation adds real elapsed time at original current-model validation entry; nested capture is retained and never subtracted. This is a diagnostic attempt, not an equivalently accelerated realtime candidate. Original functions always return their unchanged result or exception.'))
        register_imports('ACTIVATION_CAPTURE')

if __name__=='__main__':main()
