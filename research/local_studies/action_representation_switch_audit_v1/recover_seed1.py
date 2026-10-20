"""Evaluate the completed archived first replay; no second physics run."""
from common import *
import gzip,shutil
seed=20261004;native=S/'results'/NAME
if not native.exists():native.symlink_to(O,target_is_directory=True)
p=native/f'diagnostic_seed_{seed}/episode_00001';summary=json.loads((p/'summary.json').read_text());z=task_trace(p);ar=np.load(p/'SAC_ACTOR_ACTIONS.npz');t=ar['task_s'].astype(float)
cmds=[r for r in summary['online_reference_records'] if 'command_received_s' in r];assert len(t)==len(cmds)
t0=np.median([r['command_received_s']-t[i] for i,r in enumerate(cmds)]);tt=z['time_s']-t0
teacher=np.load(DEMO);x=np.tile(teacher['observations'][0],(len(t),1)).astype(float);raw=x*SCALES
for i,ts in enumerate(t):
    j=np.argmin(abs(tt-ts));assert abs(tt[j]-ts)<1e-6
    raw[i,:4]=z['estimated_human_state_rad_rad_s'][j];raw[i,4:6]=z['reference_q_rad'][j];raw[i,6:8]=z['reference_dq_rad_s'][j];raw[i,8:10]=z['reference_ddq_rad_s2'][j]
    raw[i,31:34]=z['physical_cuff_force_world_n'][j];raw[i,34:37]=z['physical_cuff_moment_world_nm'][j]
    raw[i,41:44]=[1.,0.,0.];raw[i,44]=ts;raw[i,45:47]=np.radians([120.,120.]);raw[i,47]=ts;raw[i,48]=0.
    raw[i,49:51]=ar['raw_action'][i-1] if i else [0.,0.];raw[i,51:53]=ar['executed_action'][i-1] if i else [0.,0.]
    raw[i,53]=float(ar['status'][i-1] not in ('ACCEPTED','IDENTICAL_CONTINUATION')) if i else 0.;raw[i,54]=max(0.,30.-ts)
x=(raw/SCALES).astype(np.float32);a=actor(seed);cp=W/'bc_reproduction_gate_v1/output'/f'actor_seed_{seed}.pt';a.load_state_dict(torch.load(cp,map_location='cpu',weights_only=True)['state_dict']);a.eval()
with torch.no_grad():pred=a(torch.tensor(x),deterministic=True).numpy()
maxerr=np.max(abs(pred-ar['raw_action']));save('SEED1_OBSERVATION_RECOVERY.json',dict(max_action_reprediction_error=maxerr,method='post-run reconstruct55D from archived same-boundary causal estimated/reference/measured trace, frozen model and geometry, task clock and recorded action history; teacher used only post-run for byte-identical frozen constants, no physical truth; no second physics run',observations_reconstructed=True,physics_runs_for_seed=1,exception='terminal action-evidence relative_to(R) path restriction; fixed new harness output alias only; frozen scientific sources unchanged'))
assert maxerr<2e-6,'RECOVERY_PREDICTION_MISMATCH'
np.savez_compressed(O/f'POLICY_seed_{seed}.npz',observations=x,raw_actions=ar['raw_action'],executed_actions=ar['executed_action'],task_s=t,phase=np.repeat('OUTBOUND',len(t)),status=ar['status'])
case,options=load_case_options();env=SACExpertEnv(native/'not_started',case,options,.02,'NATIVE',True);env.episode_dir=p;env.summary=summary;env.host_start=time.monotonic();env.rejections=sum(r['status'] not in ('ACCEPTED','IDENTICAL_CONTINUATION') for r in cmds);env.action_records=[dict(raw=ar['raw_action'][i].tolist(),executed=ar['executed_action'][i].tolist(),status=ar['status'][i],task_s=t[i]) for i in range(len(t))]
metric=r2.metric(env,f'DIAGNOSTIC_BC_{seed}','NATIVE');metric.pop('raw_actions');q=z['estimated_human_state_rad_rad_s'][:,:2];dq=z['estimated_human_state_rad_rad_s'][:,2:];progress=np.min(np.clip((q-np.radians([5,10]))/np.radians([115,110]),0,1),axis=1)
detail=dict(max_synchronized_progress=np.max(progress),settled_arrival=False,HOLD_entry_s=None,HOLD_completed=False,RETURN_entry_s=None,RETURN_completed=False,COMPLETE_s=None,VALID=metric['valid'],termination=summary.get('abort_reason') or summary['status'],final_q_deg=np.degrees(q[-1]),final_dq_deg_s=np.degrees(dq[-1]))
save(f'CLOSED_LOOP_seed_{seed}.json',dict(seed=seed,category='DIAGNOSTIC_NOT_OLD_GATE',metric=metric,endpoints=detail,checkpoint_sha256=sha(cp),steps=len(t),terminated=False,truncated=True,episode_dir=p,teacher_reads_during_rollout=0,teacher_overrides=0,truth_actor_inputs=False,recovered_after_report_path_exception=True,observations_reconstructed_post_run=True))
path=p/'runtime_artifacts.json';h=sha(path)
with path.open('rb') as src,gzip.open(str(path)+'.gz','wb',compresslevel=3) as dst:shutil.copyfileobj(src,dst)
with gzip.open(str(path)+'.gz','rb') as f:assert hashlib.sha256(f.read()).hexdigest()==h
path.unlink();env.close();lock();print(json.dumps(clean(dict(status='FIRST_REPLAY_RECOVERED_NO_RERUN',max_action_reprediction_error=maxerr,**detail))),flush=True)
