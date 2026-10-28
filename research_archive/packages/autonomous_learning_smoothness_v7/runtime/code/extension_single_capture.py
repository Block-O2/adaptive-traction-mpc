"""One explicit COUNTED existing-B diagnostic; never resume the closed runner."""
from extension_common import *
import os,fcntl

def main():
    guard(2700)
    from accounting import rows,record
    events=rows();starts=[r for r in events if r['event']=='START'];ended={r['id'] for r in events if r['event']=='END'}
    assert len(starts)==159 and all(r['id'] in ended for r in starts),'ONLY_LAST_UNUSED_SLOT'
    assert (STUDY/'STOP_DISPATCH').is_file(),'ORIGINAL_DISPATCH_MUST_STAY_CLOSED'
    for p in EXT.glob('ACTIVATION_INPUTS/*.pkl'):raise AssertionError('NO_CAPTURE_REPLAY')
    base=json.loads((STUDY/'queue/324_NATIVE_B_ROUTE_cold_4.json').read_text())
    id='325_NOON_B_ACTIVATION_CAPTURE';cfg=dict(base,id=id,seed=2026100844,research_profile=True,result_path=str(STUDY/'output'/(id+'_RESULT.json')),host_series='NOON_DIAGNOSTIC_CAPTURE_NOT_QUALIFICATION',capture_current_model_inputs=True,qualification_claim=False,new_public_B_repairs=0)
    cfg['source_manifest_sha256']=sha(STUDY/'CODE_MANIFEST.json')
    cfg['algorithm_sources'].update({str(STUDY/'code'/name):sha(STUDY/'code'/name) for name in ('extension_capture_worker.py','extension_single_capture.py','extension_common.py','worker.py')})
    config=EXT/'SINGLE_CAPTURE_CONFIG.json';save(config,cfg)
    plan=json.loads((EXT/'RUN_PLAN.json').read_text());plan.update(explicit_counted_diagnostic=id,remaining_physics_after_dispatch=0,diagnostic_reason='Capture exact current-model activation input at original entry, including instrumentation cost, to localize main-thread mechanics/clearance/rolling admission on actual B states. No new control or scheduling repair.');save(EXT/'RUN_PLAN.json',plan)
    begin=time.time();record('START',id,config=cfg,input_sha256=sha(config),code_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json'),extension=True)
    result=None;code=None
    try:
        code=subprocess.call([sys.executable,'-u',str(STUDY/'code/extension_capture_worker.py'),str(config)])
        p=Path(cfg['result_path']);result=json.loads(p.read_text()) if p.exists() else None
    finally:
        record('END',id,status='COMPLETE' if result is not None else 'FAILED_NO_RESULT',worker_status=None if result is None else result['status'],returncode=code,extension=True)
    save(EXT/'SINGLE_CAPTURE_RESULT.json',dict(id=id,returncode=code,worker_status=None if result is None else result['status'],wall_seconds=time.time()-begin,error=None if result is None else result.get('error'),physics_attempts_added=1,cumulative_attempts=160,qualification_claim=False,public_B_repairs_added=0))
    print(json.dumps(json.loads((EXT/'SINGLE_CAPTURE_RESULT.json').read_text())))
    assert result is not None,'DIAGNOSTIC_RESULT_MISSING'

if __name__=='__main__':main()
