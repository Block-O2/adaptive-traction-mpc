from pathlib import Path
import sys,json,os,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
S=Path('/home/hank/ihear-lab/representation_execution_v3/runtime');sys.path.insert(0,str(S/'code'))
from jitter_attribution import q
import numpy as np
def main():
 rows=[]
 for ident in ('006_B_threadCPU_nominal','007_B_threadCPU_deviation'):
  p=S/'output'/(ident+'_MULTIRATE.json')
  if not p.exists():continue
  ev=json.loads(p.read_text());fast=ev['rows']['fast'];gc=json.loads((S/'output'/(ident+'_GC_DIAGNOSTIC.json')).read_text())['rows'];starts=[r['service_start_ns'] for r in fast];gaps=np.diff(starts)/1e6;tail=[];allwork=[r for r in fast if 'diagnostic_wall_ms' in r]
  intervals=[]
  for prev,r in zip(allwork,allwork[1:]):
   if prev['diagnostic_begin_ns']!=r['diagnostic_begin_ns']:continue
   a,b=prev['diagnostic_end_ns'],r['diagnostic_end_ns'];wall=(b-a)/1e6;cpu=r['diagnostic_thread_cpu_ms']-prev['diagnostic_thread_cpu_ms'];assert cpu>=0 and wall>0
   g=[z for z in gc if z['begin_ns']<b and z['finish_ns']>a]
   item=dict(begin_ns=a,finish_ns=b,phase=r['phase'],physical_time_s=r['physics_start_s'],wall_ms=wall,threadCPU_ms=cpu,offCPU_including_original_scheduled_wait_ms=max(0,wall-cpu),GC=g)
   intervals.append(item)
   if wall>7.5:tail.append(item|dict(classification='CPU_work_supported' if cpu>5 and cpu>=.8*wall else ('offCPU_including_scheduled_wait_supported' if wall-cpu>2 else 'mixed_or_unresolved')))
  axis=json.loads((S/'reports'/(ident+'_AXES.json')).read_text())
  row=dict(id=ident,scope='attribution-only pre-next-tick-marker to pre-next-tick-marker spans, including scheduled wait and physical catch-up; never substitutes lean FAST qualification',FAST_gap_ms=q(gaps),marker_interval_wall_ms=q([r['wall_ms'] for r in intervals]),marker_interval_threadCPU_ms=q([r['threadCPU_ms'] for r in intervals]),marker_interval_offCPU_ms=q([r['offCPU_including_original_scheduled_wait_ms'] for r in intervals]),GC_events=len(gc),GC_overlap_tail=sum(bool(r['GC']) for r in tail),tails=tail,classifications=dict(collections.Counter(r['classification'] for r in tail)),physical=axis['PHYSICAL_TASK_VALID'],causal=axis['HOST_EXECUTION_CAUSAL_VALID'],invalidated_measurement='capture wrapper was installed after commissioning loop globals cloned, so raw diagnostic CPU/wall values are cumulative from an earlier capture, not exclusive owner spans; adjacent marker differences within the same capture anchor are valid elapsed CPU/wall observations')
  rows.append(row);print(json.dumps({k:row[k] for k in ('id','FAST_gap_ms','marker_interval_wall_ms','marker_interval_threadCPU_ms','marker_interval_offCPU_ms','GC_events','classifications')}),flush=True)
 target=S/'reports/THREAD_CPU_JITTER_DIAGNOSTICS.json'
 if target.exists() and not (S/'reports/THREAD_CPU_JITTER_DIAGNOSTICS_v1_INVALID_OWNER_SCOPE.json').exists():
  (S/'reports/THREAD_CPU_JITTER_DIAGNOSTICS_v1_INVALID_OWNER_SCOPE.json').write_bytes(target.read_bytes())
 target.write_text(json.dumps(dict(status='ADJACENT_MARKER_CPU_WALL_OBSERVATIONS_ONLY',rows=rows,historical_slow_run_causation='NOT_IDENTIFIED_BY_NEW_FAST_RUNS',no_profiler=True,no_controller_math_changes=True),indent=2)+'\n')
if __name__=='__main__':main()
