"""Bounded streaming extraction of native runtime arrays, no full JSON copy."""
from task_bootstrap import *
import gzip,numpy as np
def array_items(path,key):
 with gzip.open(path,'rt') as f:
  buf='';needle='"'+key+'":';found=False;decoder=json.JSONDecoder()
  while not found:
   part=f.read(65536)
   if not part:return
   buf+=part;pos=buf.find(needle)
   if pos>=0:
    buf=buf[pos+len(needle):].lstrip()
    while not buf:buf+=f.read(65536);buf=buf.lstrip()
    if not buf.startswith('['):raise ValueError('NOT_ARRAY:'+key)
    buf=buf[1:];found=True
   else:buf=buf[-len(needle):]
  while True:
   buf=buf.lstrip(', \n\r\t')
   if buf.startswith(']'):return
   try:value,end=decoder.raw_decode(buf)
   except json.JSONDecodeError:
    part=f.read(65536)
    if not part:raise ValueError('INCOMPLETE_ARRAY:'+key)
    buf+=part
    if len(buf)>4*2**20:raise ValueError('ITEM_EXCEEDS_BOUNDED_EXTRACTION:'+key)
    continue
   yield value;buf=buf[end:]
def main():
 id=sys.argv[1];path=STUDY/'source/results'/id/'runtime_artifacts.json.gz';times=[];cmds=[]
 for row in array_items(path,'native_states_evaluation_only'):
  if 'host_step_finish_ns' in row:times.append((row['host_step_finish_ns']-row['host_step_start_ns'])/1e6)
 for row in array_items(path,'command_receipts'):
  if row.get('applied'):
   cmds.append({k:row.get(k) for k in ('receipt_index','source_capture_ns','effective_activation_ns','conservative_activation_ns','source_sample_time_s','start_physics_s','end_physics_s','native_steps','sensor_age_at_apply_ms','host_sensor_age_at_apply_ms_profile','cancelled_before_write_reason','request_id','plan_request_id','reference_source','command_kind')})
 out=dict(id=id,native_step_host_ms=dict(n=len(times),p50=float(np.quantile(times,.5)),p95=float(np.quantile(times,.95)),max=max(times),mean=float(np.mean(times)),registered_physics_dt_ms=.25,mean_step_compute_fraction_of_dt=float(np.mean(times)/.25)) if times else None,applied_receipts=cmds,no_trajectory_replay=True,no_truth_in_controller=True)
 save(STUDY/'reports'/(id+'_STREAM_EXECUTION_EVIDENCE.json'),out);print(json.dumps(dict(id=id,native_step_host_ms=out['native_step_host_ms'],applied_receipt_count=len(cmds))))
if __name__=='__main__':main()
