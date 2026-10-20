"""Frozen actual-entry input replays; no plant and no qualification inference."""
from extension_common import *
import pickle,math,cProfile,pstats,numpy as np

def eq(a,b):
    if isinstance(a,dict):return isinstance(b,dict) and set(a)==set(b) and all(eq(a[k],b[k]) for k in a)
    if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(eq(x,y) for x,y in zip(a,b))
    if isinstance(a,(int,float)) and not isinstance(a,bool):
        return isinstance(b,(int,float)) and (a==b or math.isnan(a) and math.isnan(b) or math.isfinite(a) and math.isfinite(b) and abs(a-b)<=1e-10)
    return a==b

def differences(a,b,prefix=''):
    if eq(a,b):return []
    if isinstance(a,dict) and isinstance(b,dict):
        return [x for k in sorted(set(a)|set(b)) for x in (differences(a[k],b[k],prefix+'/'+k) if k in a and k in b else [prefix+'/'+k+':MISSING_KEY'])]
    if isinstance(a,list) and isinstance(b,list) and len(a)==len(b):return [x for i,(v,w) in enumerate(zip(a,b)) for x in differences(v,w,prefix+'/'+str(i))]
    return [prefix]

def main():
    guard(1800);begin=time.time();before=sha(STUDY/'ATTEMPTS.jsonl')
    import study_common as sc
    from extension_timer_service import warm
    warm('T0')
    from traction_mpc_stage5.full3d_adaptive_integration_v1 import activation_validation as av
    import profiling_instrumentation as pi
    from causal_timing_report import quantile
    manifest=json.loads((EXT/'ACTIVATION_INPUT_MANIFEST.json').read_text());rows=[];references=[]
    for item in manifest['rows']:
        path=Path(item['path']);assert sha(path)==item['sha256'];record=pickle.loads(path.read_bytes())
        if record['payload'] is None:
            rows.append(dict(index=item['index'],status='INPUT_CAPTURE_FAILED',error=record['capture_error']));references.append(None);continue
        function=getattr(av,record['name']);elapsed=[];cpu=[];outputs=[]
        for repeat in range(8):
            args,kwargs=pickle.loads(record['payload']);start=time.monotonic_ns();cstart=time.thread_time_ns()
            try:value=function(*args,**kwargs);error=None
            except BaseException as e:value=None;error=type(e).__name__+':'+str(e)
            finish=time.monotonic_ns();cfinish=time.thread_time_ns();elapsed.append((finish-start)/1e6);cpu.append((cfinish-cstart)/1e6);outputs.append(dict(error=error,result=sc.clean(value)))
        repeatable=all(eq(outputs[0],x) for x in outputs[1:]);assert repeatable,'ORIGINAL_INPUT_REPLAY_NOT_REPEATABLE'
        expected=dict(error=record['original_error'],result=sc.clean(record['result']));diff=differences(outputs[0],expected)
        rows.append(dict(index=item['index'],name=record['name'],phase=record['phase'],snapshot=str(path),sha256=item['sha256'],first_elapsed_ms=elapsed[0],warm_elapsed_ms=quantile(elapsed[1:]),warm_thread_cpu_ms=quantile(cpu[1:]),repeatable_original_output=repeatable,captured_final_record_equal=not diff,captured_final_record_differences=diff,original_error=outputs[0]['error'],feasible=None if outputs[0]['result'] is None else outputs[0]['result'].get('feasible'),argument_types={k:type(v).__module__+'.'+type(v).__qualname__ for k,v in kwargs.items()},capture_ms=item['capture_ms'],actual_original_with_nested_capture_ms=item['original_with_nested_capture_ms']))
        references.append(outputs[0])
    pi.install()
    for item,row,reference in zip(manifest['rows'],rows,references):
        if reference is None:continue
        record=pickle.loads(Path(item['path']).read_bytes());args,kwargs=pickle.loads(record['payload']);pi.EVENTS.clear();profile=cProfile.Profile();profile.enable()
        try:value=getattr(av,record['name'])(*args,**kwargs);error=None
        except BaseException as e:value=None;error=type(e).__name__+':'+str(e)
        profile.disable();assert eq(reference,dict(error=error,result=sc.clean(value)))
        stats=pstats.Stats(profile);row['profile_events']=list(pi.EVENTS);row['cprofile_top']=[dict(path=p,line=line,function=name,primitive_calls=cc,total_calls=nc,self_ms=tt*1000,cumulative_ms=ct*1000) for (p,line,name),(cc,nc,tt,ct,callers) in sorted(stats.stats.items(),key=lambda x:x[1][3],reverse=True)[:45]]
    # Existing C2 is diagnostic-only here, not a third promoted public repair.
    import batched_mechanics
    batched_mechanics.install(dict(public_version='C2',execution_mode='OFFLINE_NO_PHYSICS'))
    for item,row,reference in zip(manifest['rows'],rows,references):
        if reference is None:continue
        record=pickle.loads(Path(item['path']).read_bytes());values=[];same=[]
        for repeat in range(8):
            args,kwargs=pickle.loads(record['payload']);t=time.monotonic_ns()
            try:value=getattr(av,record['name'])(*args,**kwargs);error=None
            except BaseException as e:value=None;error=type(e).__name__+':'+str(e)
            finish=time.monotonic_ns();values.append((finish-t)/1e6);same.append(eq(reference,dict(error=error,result=sc.clean(value))))
        row.update(existing_C2_diagnostic_elapsed_ms=quantile(values),existing_C2_original_complete_output_equal=all(same),existing_C2_no_promotion=True)
    assert sha(STUDY/'ATTEMPTS.jsonl')==before
    register_imports('ACTIVATION_REPLAY')
    old=EXT/'ACTIVATION_REPLAY.json'
    if old.exists():shutil.copy2(old,EXT/('ACTIVATION_REPLAY_HISTORY_'+sha(old)+'.json'))
    out=dict(status='OFFLINE_ACTIVATION_INPUTS_LOCALIZED' if rows else 'CENSORED_ACTIVATION_ENTRY_NOT_REACHED',rows=rows,captures=len(rows),input_capture_failures=sum(r.get('status')=='INPUT_CAPTURE_FAILED' for r in rows),captured_final_record_mismatches=sum(r.get('captured_final_record_equal') is False for r in rows) if rows else None,existing_C2_output_mismatches=sum(r.get('existing_C2_original_complete_output_equal') is False for r in rows) if rows else None,physics_attempts_added=0,actual_physics_steps_added=0,Q_updates=0,wall_seconds=time.time()-begin,interpretation='No capture means the actual failed prefix did not reach the patched activation entry; replay/equivalence/latency are censored, not zero-cost or PASS. If present, exact immutable original function-entry bytes are replayed after physics ended. Captured outputs held by reference can be extended by outer native code; mismatches are retained. Existing C2 is diagnostic only. No measurement is subtracted from actual host latency; no deployment/qualification/promotion claim.')
    save(EXT/'ACTIVATION_REPLAY.json',out);print(json.dumps({k:out[k] for k in ('status','captures','input_capture_failures','captured_final_record_mismatches','existing_C2_output_mismatches','wall_seconds')}))

if __name__=='__main__':main()
