"""Attribution-only thread CPU and GC observations, no profiler or JSON I/O."""
import time,gc
GC=[];BEGIN=None;CYCLE=None
def callback(phase,info):
 global BEGIN
 if phase=='start':BEGIN=(time.monotonic_ns(),time.thread_time_ns(),info.get('generation'))
 elif BEGIN is not None:
  GC.append(dict(begin_ns=BEGIN[0],finish_ns=time.monotonic_ns(),thread_cpu_ns=time.thread_time_ns()-BEGIN[1],generation=BEGIN[2],collected=info.get('collected')));BEGIN=None
def install():
 import study_common as sc,multirate
 from traction_mpc_stage5.full3d_adaptive_integration_v1.wall_physics import WallPhysicsSession as C
 original_capture=sc.rt._capture_boundary;original_next=C.next_control_tick
 def capture(runtime):
  global CYCLE
  start=time.monotonic_ns();cpu=time.thread_time_ns();value=original_capture(runtime)
  CYCLE=(start,cpu,time.monotonic_ns(),time.thread_time_ns());return value
 def next_tick(self):
  if CYCLE is not None and multirate.ROWS['fast']:
   r=multirate.ROWS['fast'][-1]
   if 'diagnostic_thread_cpu_ms' not in r:
    now=time.monotonic_ns();cpu=time.thread_time_ns()
    r.update(diagnostic_begin_ns=CYCLE[0],diagnostic_end_ns=now,diagnostic_wall_ms=(now-CYCLE[0])/1e6,diagnostic_thread_cpu_ms=(cpu-CYCLE[1])/1e6,diagnostic_capture_wall_ms=(CYCLE[2]-CYCLE[0])/1e6,diagnostic_capture_cpu_ms=(CYCLE[3]-CYCLE[1])/1e6)
  return original_next(self)
 sc.rt._capture_boundary=capture;C.next_control_tick=next_tick;gc.callbacks.append(callback)
def finish(ident):
 from study_common import save
 if callback in gc.callbacks:gc.callbacks.remove(callback)
 save(ident+'_GC_DIAGNOSTIC.json',dict(rows=GC,scope='GC callback and per service main thread CPU; attribution-only, not formal FAST benchmark'))
