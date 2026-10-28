from pathlib import Path
import os,sys,json,hashlib,bisect,collections
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
sys.dont_write_bytecode=True
S=Path('/home/hank/ihear-lab/constraint_geometry_learning_v4/runtime');sys.path.insert(0,str(S/'code'))
import numpy as np
from stream_runtime_evidence import array_items
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(2**20):h.update(b)
 return h.hexdigest()
def q(a):return dict(n=len(a),**dict(zip(('p50','p95','p99','max'),np.percentile(a,[50,95,99,100]).tolist()))) if len(a) else dict(n=0)
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def analyze(folder,ident):
 ev=json.loads((folder/'output'/(ident+'_MULTIRATE.json')).read_text());cfg=json.loads((folder/'output'/(ident+'_RESULT.json')).read_text())['inputs'];fast=ev['rows']['fast'];reqs=ev['native_requests']
 co=json.loads((folder/'output'/(ident+'_COMMISSIONING_OWNER.json')).read_text());ipc=json.loads((folder/'output'/(ident+'_DIRECT_IPC.json')).read_text());windows=[]
 for r in reqs:
  if r.get('asynchronous') and r.get('worker_start_ns') and r.get('compute_finish_ns'):windows.append((r['worker_start_ns'],r['compute_finish_ns'],'TASK',r['request_id']))
 for r in co.get('rows',[]):
  if r.get('worker_start_ns') and r.get('estimate_ready_ns'):windows.append((r['worker_start_ns'],r['estimate_ready_ns'],'COMMISSIONING',r.get('request_id')))
 starts=np.asarray([r['service_start_ns'] for r in fast],dtype=np.int64);gaps=np.diff(starts)/1e6
 with np.load(folder/'source/results'/ident/'trace.npz') as z:
  trace_t=z['time_s'].copy();trace_phase=z['task_phase'].copy()
 task_phases=[]
 for r in fast:
  index=max(0,min(len(trace_t)-1,int(np.searchsorted(trace_t,r['physics_start_s'],side='right')-1)))
  task_phases.append(str(trace_phase[index]) if r['phase']=='TASK' else r['phase'])
 artifact=folder/'source/results'/ident/'runtime_artifacts.json.gz'
 stepstart=[];stepfinish=[];stepdt=[]
 for r in array_items(artifact,'native_states_evaluation_only'):
  stepstart.append(r['host_step_start_ns']);stepfinish.append(r['host_step_finish_ns']);stepdt.append((r['host_step_finish_ns']-r['host_step_start_ns'])/1e6)
 cumulative=np.r_[0,np.cumsum(stepdt)]
 collect=sorted(r['collected_ns'] for r in ipc['rows'] if r['event']=='COLLECT')
 groups=collections.defaultdict(list);tails=[];changes={i for i in range(1,len(fast)) if task_phases[i]!=task_phases[i-1]}
 for i,gap in enumerate(gaps):
  a,b=int(starts[i]),int(starts[i+1]);r=fast[i];active=[w for w in windows if w[0]<b and w[1]>a];stage=task_phases[i];groups[stage].append(float(gap));groups['planner_active' if active else 'planner_idle'].append(float(gap))
  if gap<=7.5:continue
  j,k=bisect.bisect_left(stepstart,a),bisect.bisect_left(stepstart,b);physics_ms=float(cumulative[k]-cumulative[j]);work=(r['service_finish_ns']-a)/1e6
  sends=[x for x in ipc['rows'] if x['event']=='SUBMIT' and a<=x['start_ns']<b]
  descheduled_sends=[x for x in sends if x.get('send_wall_ns',0)>2_000_000 and x.get('send_thread_cpu_ns',0)<.2*x['send_wall_ns']]
  annotations=[]
  if physics_ms>.5*gap and k-j>25:annotations.append('physics_catch_up_supported')
  if any(abs(i-jj)<=2 for jj in changes):annotations.append('transition_specific_condition')
  if descheduled_sends:annotations.append('IPC_host_wait_supported_by_wall_CPU_difference')
  if not annotations:annotations.append('owner_work_or_host_scheduling_unresolved')
  tails.append(dict(service_index=i,gap_ms=float(gap),threshold_gt10=bool(gap>10),threshold_gt15=bool(gap>15),phase=stage,next_phase=fast[i+1]['phase'],source_physical_time_s=r['physics_start_s'],planner_active_windows=[dict(stage=w[2],request_id=w[3],begin_ns=w[0],finish_ns=w[1]) for w in active],native_physics_steps=k-j,native_physics_host_compute_sum_ms=physics_ms,native_physics_host_extent_ms=0 if j==k else (stepfinish[k-1]-stepstart[j])/1e6,owner_work_span_ms=work,sensor_capture_and_precatch_span_ms=(r['sensor_finish_ns']-a)/1e6,feedback_to_owner_finish_span_ms=(r['service_finish_ns']-r['feedback_start_ns'])/1e6,post_owner_to_next_service_ms=(b-r['service_finish_ns'])/1e6,receipt_index=r.get('receipt_index'),IPC_collections_in_interval=bisect.bisect_left(collect,b)-bisect.bisect_left(collect,a),IPC_submit=sends,admission_spans=[dict(begin_ns=x['revalidation_start_ns'],finish_ns=x['revalidation_finish_ns'],feasible=x['feasible']) for x in ev['rows']['admission'] if x['revalidation_start_ns']<b and x['revalidation_finish_ns']>a],preceding_gap_ms=None if i==0 else float(gaps[i-1]),following_gap_ms=None if i+1>=len(gaps) else float(gaps[i+1]),physics_before_wait_s=r['physics_before_wait_s'],physical_finish_s=r['physical_finish_s'],skipped_periods=r['skipped_periods'],annotations=annotations,GC='UNOBSERVED',thread_CPU_service='UNOBSERVED',controller_observer_receipt_exclusive='NOT_SEPARATELY_OBSERVED'))
 rolling=[];first=0
 for last in range(1,len(starts)):
  while first<last-1 and starts[last]-starts[first+1]>=1_000_000_000:first+=1
  if starts[last]-starts[first]>=990_000_000:rolling.append(float((starts[last]-starts[first])/(last-first)/1e6))
 row=dict(id=ident,folder=str(folder),service_count=len(fast),FAST_gap_ms=q(gaps),owner_work_ms=q([(r['service_finish_ns']-r['service_start_ns'])/1e6 for r in fast]),sensor_and_precatch_ms=q([(r['sensor_finish_ns']-r['service_start_ns'])/1e6 for r in fast]),feedback_to_owner_finish_ms=q([(r['service_finish_ns']-r['feedback_start_ns'])/1e6 for r in fast]),native_step_compute_ms=q(stepdt),rolling_1s_ms=q(rolling),miss_fraction=sum(r['skipped_periods'] for r in fast)/(len(fast)+sum(r['skipped_periods'] for r in fast)),phase_condition_gap_ms={k:q(v) for k,v in groups.items()},tails_gt7_5=len(tails),tails_gt10=int(np.sum(gaps>10)),tails_gt15=int(np.sum(gaps>15)),tail_annotations=dict(collections.Counter(a for r in tails for a in r['annotations'])),config=cfg,raw_hashes={str(p.relative_to(folder)):sha(p) for p in [artifact,folder/'output'/(ident+'_MULTIRATE.json'),folder/'source/results'/ident/'config_snapshot.json']},FAST_measurement_semantics=sorted(set(r['service_finish_semantics'] for r in fast)))
 save(S/'reports'/(ident+'_JITTER_CYCLES.json'),dict(summary=row,anomalous_cycles=tails))
 return row
def main():
 rows=[]
 for folder,ids in [(S.parent/'b_hold_return_critical_path_v1',['047_C13_host_nominal_quiet','048_C13_host_deviation_quiet']),(S.parent/'b_runtime_qualification_decoupling_v1',['002_B_confirm_deviation','003_B_confirm_nominal_harness_retry','004_B_quiet_retest_nominal','005_B_quiet_retest_deviation'])]:
  for ident in ids:
   row=analyze(folder,ident);rows.append(row);print(json.dumps({k:row[k] for k in ('id','FAST_gap_ms','owner_work_ms','native_step_compute_ms','tail_annotations')}),flush=True)
 old=S.parent/'b_hold_return_critical_path_v1';new=S.parent/'b_runtime_qualification_decoupling_v1';comparison=[]
 manifest=json.loads((new/'FINAL_CODE_MANIFEST.json').read_text())
 for rel in manifest:
  if rel.split('/')[0] not in ('source','deps','code','native','build') or 'results' in Path(rel).parts:continue
  a,b=old/rel,new/rel
  if not a.exists():comparison.append(dict(path=rel,status='ADDED_HARNESS'));continue
  if sha(a)==sha(b):continue
  if a.suffix=='.py':
   expected=a.read_text().replace(str(old),str(new)).replace('"b_hold_return_critical_path_v1"','"b_runtime_qualification_decoupling_v1"').replace("'b_hold_return_critical_path_v1'","'b_runtime_qualification_decoupling_v1'")
   if expected==b.read_text():continue
  comparison.append(dict(path=rel,status='DIFFERENCE_REQUIRES_REVIEW',old_sha=sha(a),new_sha=sha(b)))
 config_differences=[]
 for a,b in [(rows[1],rows[2]),(rows[0],rows[3]),(rows[0],rows[4]),(rows[1],rows[5])]:
  keys=set(a['config'])|set(b['config']);diff={k:[a['config'].get(k),b['config'].get(k)] for k in keys if a['config'].get(k)!=b['config'].get(k)};config_differences.append(dict(a=a['id'],b=b['id'],differences=diff))
 save(S/'reports/HISTORICAL_JITTER_ATTRIBUTION.json',dict(status='READ_ONLY_ATTRIBUTION_COMPLETE',rows=rows,source_nonrelocation_differences=comparison,config_differences=config_differences,native_binary_old={str(p.name):sha(p) for p in (old/'build').rglob('*.so')},native_binary_new={str(p.name):sha(p) for p in (new/'build').rglob('*.so')},unresolved=['Per-service main thread CPU, GC and exact descheduling not recorded historically','Exclusive controller, observer, feedback, receipt and physics waits cannot be inferred from one aggregate owner span','Power mode/Windows scheduling causation not established']))
if __name__=='__main__':main()
