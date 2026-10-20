from study_common import *
from task_bootstrap import save as write
def main():
 metric=read('003_zero_interface_retry1_RESULT.json')['metric'];folder=R/Path(metric['trace']).parent
 summary=json.loads((folder/'summary.json').read_text());found=[]
 def walk(x,path):
  if isinstance(x,dict):
   if 'compute_ms' in x:found.append(dict(path=path,**{k:v for k,v in x.items() if k in ('stage','compute_ms','activation_age_ms','outcome','snapshot_ms','worker_scheduling_ms','validation_and_command_construction_ms','validation_scheduling_ms','source_sample_time_s','request_id')}))
   for k,v in x.items():walk(v,path+'/'+k)
  elif isinstance(x,list):
   for i,v in enumerate(x):walk(v,path+'/'+str(i))
 walk(summary,'summary')
 if not found:
  import gzip
  with gzip.open(folder/'runtime_artifacts.json.gz','rt') as f:artifact=json.load(f)
  walk(artifact,'runtime')
 write(STUDY/'TIMING_BASELINE.json',dict(rows=found,bridge_s=.04,activation_score_gate_s=.055,generic_expiration_s=.100,source='runtime native endpoint bridge, online_planning PlanLifecycle, frozen physical qualification activation gate',coordination_end_to_end='context/candidate generation/G/Q/native candidate checks/submission + subsequent snapshot, native worker scheduling/compute, current-model revalidation and command receipt',allowed_early_compute='only before actual endpoint with a causally valid candidate-independent snapshot if ownership proves it; current hook has no such advance',replay='reject decisions that cannot arrive before the unchanged bridge/activation deadlines; preserve valid carry; no stale action backwrite; scientific mode does not charge host wall to physics',baseline_metric=metric))
 print(json.dumps(dict(folder=str(folder),timing_rows=len(found),examples=found[:4])))
if __name__=='__main__':main()
