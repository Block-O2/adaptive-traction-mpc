"""Isolated attribution only: exact compiled callback bindings, no control changes."""
import sys, os, time, json, threading
from pathlib import Path
sys.dont_write_bytecode=True
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1')
sys.path.insert(0,str(S/'code'))
import multirate,commissioning_owner,run_one
STARTS={};ROWS=[];BINDING={};CAPTURE_CALLS=0
def sched():return [int(x) for x in Path('/proc/thread-self/schedstat').read_text().split()]
def finish_row(row,kind):
    if row is None or row.get('diagnostic_complete'):return
    begin=STARTS.get(row['service_start_ns'])
    if begin is None:return
    end_wall=time.monotonic_ns();end_cpu=time.thread_time_ns();end_sched=sched()
    row.update(diagnostic_complete=True,diagnostic_begin_wall_ns=begin['wall'],diagnostic_end_wall_ns=end_wall,diagnostic_thread_cpu_ms=(end_cpu-begin['cpu'])/1e6,diagnostic_scheduler_runqueue_wait_ms=(end_sched[1]-begin['sched'][1])/1e6,diagnostic_sched_cpu_ms=(end_sched[0]-begin['sched'][0])/1e6,diagnostic_wall_ms=(end_wall-begin['wall'])/1e6,diagnostic_begin_bracket_overhead_ns=row['service_start_ns']-begin['wall'],diagnostic_thread_id=begin['tid'],diagnostic_end_scope=kind)
    ROWS.append(row)
original_multirate=multirate.install
def install_multirate(revision,mode):
    original_multirate(revision,mode)
    import study_common as sc
    capture_original=sc.rt._capture_boundary;interval_original=sc.rt._execute_interval
    def capture(runtime):
        global CAPTURE_CALLS
        wall=time.monotonic_ns();cpu=time.thread_time_ns();wait=sched();tid=threading.get_native_id()
        value=capture_original(runtime);CAPTURE_CALLS+=1
        marker=runtime.get('_mr_latest_capture',{}).get('start_ns')
        if marker is not None:STARTS[marker]=dict(wall=wall,cpu=cpu,sched=wait,tid=tid)
        return value
    def interval(runtime,**kwargs):
        before=len(multirate.ROWS['fast'])
        try:return interval_original(runtime,**kwargs)
        finally:
            if len(multirate.ROWS['fast'])>before:finish_row(multirate.ROWS['fast'][-1],'actual interval return after original service_finish; no scheduled next-tick wait included')
    sc.rt._capture_boundary=capture;sc.rt._execute_interval=interval
    BINDING['installed_capture']=capture;BINDING['installed_interval']=interval
multirate.install=install_multirate
original_commissioning=commissioning_owner.install
def install_commissioning(revision,mode):
    original_commissioning(revision,mode)
    import study_common as sc
    from traction_mpc_stage5.full3d_adaptive_integration_v1.wall_physics import WallPhysicsSession
    active=sc.rt._run_executed_case.__globals__
    assert active['_capture_boundary'] is BINDING['installed_capture'],'INVALID_COMPILED_CAPTURE_BINDING'
    original_tick=WallPhysicsSession.next_control_tick
    def tick(self):
        row=multirate.ROWS['fast'][-1] if multirate.ROWS['fast'] else None
        if row is not None and row.get('service_finish_ns') is None:finish_row(row,'before original C2b service_finish marker and scheduled wait/catch-up')
        return original_tick(self)
    WallPhysicsSession.next_control_tick=tick
    BINDING['verified_before_physical_epoch']=True
    BINDING['compiled_filename']=sc.rt._run_executed_case.__code__.co_filename
commissioning_owner.install=install_commissioning
def main():
    cfg=json.loads(Path(sys.argv[1]).read_text());ident=cfg['id']
    try:run_one.main(cfg)
    finally:
        serial=[]
        for row in ROWS:
            serial.append({k:v for k,v in row.items() if k.startswith('diagnostic_') or k in ('service_start_ns','service_finish_ns','stage','phase','skipped_periods','lateness_ns')})
            serial[-1]['diagnostic_end_marker_offset_ns']=row['diagnostic_end_wall_ns']-row['service_finish_ns'] if row.get('service_finish_ns') is not None else None
        out=dict(status='PASS' if BINDING.get('verified_before_physical_epoch') and len(serial)==len(multirate.ROWS['fast']) else 'PARTIAL',rows=serial,total_actual_services=len(multirate.ROWS['fast']),covered_services=len(serial),capture_calls=CAPTURE_CALLS,compiled_capture_binding_verified_before_physics=BINDING.get('verified_before_physical_epoch'),compiled_filename=BINDING.get('compiled_filename'),scope='Actual compiled runtime plus original commissioning service closure; thread CPU and Linux schedstat at synchronous same-service bracketing boundaries. Captures small instrumentation overhead and may alter timing; excluded from all primary pairs.',scheduler_wait_semantics='Linux /proc/thread-self/schedstat second field: runnable runqueue wait; wall-minus-threadCPU also contains blocking and measurement mismatch, never equated to scheduler wait',control_safety_lifecycle_changes=False)
        (S/'output'/(ident+'_COMPILED_FAST_DIAGNOSTIC.json')).write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
