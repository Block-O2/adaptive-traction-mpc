"""SCI-only deployable snapshots, buffered until after all physical work."""
import pickle,time
from native_core import snapshot_task_call
ROWS=[]
def capture(interface,b,c):
 if not interface.request.get('capture_states'):return
 assert interface.request['execution_mode']=='SCIENTIFIC_SIMULATION','NO_CRITICAL_PATH_STATE_LOGGING'
 req=b['request'];ROWS.append(dict(request_id=req.request_id,sensor_capture_ns=req.sensor_capture_ns,request_ns=req.request_ns,context=c,count=interface.count.copy(),carry=interface.carry.copy(),rng_state=interface.rng.bit_generator.state,payload=snapshot_task_call(b['adaptive_planner'],b['arguments']),model_hash=interface.model_hash,authority='existing native modifiable boundary only',observation_role='deployable causal; no physical truth fields'))
def finish(id):
 if not ROWS:return
 from task_bootstrap import STUDY,sha,save
 root=STUDY/'output/STATE_SNAPSHOTS'/id;root.mkdir(parents=True,exist_ok=False);out=[]
 for i,row in enumerate(ROWS):
  p=root/f'{i:03d}.pkl';p.write_bytes(pickle.dumps(row,protocol=5));out.append(dict(path=str(p),sha256=sha(p),request_id=row['request_id'],count=row['count'],model_hash=row['model_hash']))
 save(root/'MANIFEST.json',dict(rows=out,written_after_physics=True,no_future_truth=True))
