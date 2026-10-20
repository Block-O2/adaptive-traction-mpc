from pathlib import Path
import sys,json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');sys.path.insert(0,str(Path(__file__).resolve().parent))
from host_review import scalars
ident=sys.argv[1];rows=json.loads((S/'output'/(ident+'_DIRECT_IPC.json')).read_text())['rows'];warm=[r for r in rows if r['event']=='D2_BIDIRECTIONAL_TRANSPORT_WARM'];submits=[r for r in rows if r['event']=='SUBMIT'];artifact=S/'source/results'/ident/'runtime_artifacts.json.gz'
epoch=scalars(artifact,['epoch_ns']).get('epoch_ns') if artifact.exists() else None
mode=json.loads((S/'output'/(ident+'_RESULT.json')).read_text())['inputs']['execution_mode']
checks=dict(exactly_one_warm=len(warm)==1,all_TASK_identities_start_at_one=bool(submits) and submits[0]['identity']==1,worker_joined=any(r['event']=='JOIN' and r.get('joined') for r in rows))
if mode=='REALTIME_CHARACTERIZATION':
 if epoch is not None:checks['warm_finished_before_physical_epoch']=bool(warm and warm[0]['finish_ns']<epoch)
 else:checks['physical_epoch_available']=False
out=dict(id=ident,status='PASS' if all(checks.values()) else 'FAIL_OR_UNVERIFIED',checks=checks,physical_epoch_ns=epoch,warm=warm,first_TASK_submit=submits[:1],maximum_TASK_send_wall_ns=max((r['send_wall_ns'] for r in submits),default=None),maximum_TASK_send_thread_cpu_ns=max((r['send_thread_cpu_ns'] for r in submits),default=None),physics_steps=0,model_API_calls=0,unix=time.time(),scope='Observed startup and actual transmit timing, no claim warm mathematically guarantees syscall latency.')
out['mode']=mode
if mode=='SCIENTIFIC_SIMULATION':
 out['status']='SCI_PROTOCOL_CHECKS_PASS_HOST_ORDERING_NOT_TESTED' if all(checks.values()) else out['status']
 out['scientific_epoch_semantics']='Original _start_scientific_session_epoch creates the simulation epoch BEFORE lifecycle process warm, then captures initial sample. Comparing real host warm ns to that simulated epoch does not test realtime ordering. Real host runs still require warm finish strictly before WallPhysicsSession epoch; no threshold changed.'
(S/'reports'/(ident+'_TRANSPORT_WARM_AUDIT.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
