from common import *
class Recorder:
 replay_mode=False
 def __init__(self):self.rows=[];self.spec=None
 def boundary(self,b):
  r=b['reference'];self.spec=b['spec']
  self.rows.append(dict(phase=b['task_state'].phase.value,t=float(b['physical_now']-b['task_start_time']),q=r.q_rad.copy(),v=r.dq_rad_s.copy(),a=r.ddq_rad_s2.copy()))
 def finish(self,env,metric):
  np.savez_compressed(L/'B_TAPE.npz',phase=[x['phase'] for x in self.rows],t=[x['t'] for x in self.rows],q=[x['q'] for x in self.rows],v=[x['v'] for x in self.rows],a=[x['a'] for x in self.rows])
  shutil.copy2(L/'B_TAPE.npz',D/'B_TAPE.npz')
  save('B_FREEZE.json',dict(version='R2_old_nominal_current_source_frozen_v1',runtime_sha256=sha(S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py'),model_mode='commissioning_only',task_spec=self.spec,metric=metric,tape_sha256=sha(L/'B_TAPE.npz')))
if __name__=='__main__':
 if not (L/'B_original.json').exists():run('B_original',original=True)
 if not (L/'B_zero_interface.json').exists():
  rec=Recorder();run('B_zero_interface',rec)
 else:
  save('B_FREEZE.json',dict(version='R2_old_nominal_current_source_frozen_v1',runtime_sha256=sha(S/'src/traction_mpc_stage5/full3d_adaptive_integration_v1/runtime_sac_expert_v1.py'),model_mode='commissioning_only',task_spec_source='B run summary and protected task.py/configs',metric=read('B_zero_interface.json'),tape_sha256=sha(L/'B_TAPE.npz')))
 a=np.load(O/'B_original/trace.npz');b=np.load(O/'B_zero_interface/trace.npz')
 errors={};mismatches=[]
 for k in a.files:
  if k not in b.files or a[k].shape!=b[k].shape:mismatches.append(k);continue
  if a[k].dtype.kind in 'fiu':
   if not np.array_equal(np.isnan(a[k]),np.isnan(b[k])):mismatches.append(k)
   finite=np.isfinite(a[k])&np.isfinite(b[k]);errors[k]=float(np.max(np.abs(a[k][finite]-b[k][finite]))) if np.any(finite) else 0.
  elif not np.array_equal(a[k],b[k]):mismatches.append(k)
 ma=read('B_original.json');mb=read('B_zero_interface.json')
 gate=dict(pass_=not mismatches and all(e<=1e-10 for e in errors.values()) and abs(ma['J_F']-mb['J_F'])<=1e-6 and ma['valid'] and mb['valid'],mismatches=mismatches,array_errors=errors,J_F_error=abs(ma['J_F']-mb['J_F']),matched=mb['matched_eligible'])
 save('GATE_A.json',gate);print(json.dumps(gate),flush=True)
