from common import *
def main():
 z=np.load(L/'B_TAPE.npz');rows=[]
 for phase in ('OUTBOUND','HOLD','RETURN'):
  mask=z['phase']==phase;t=z['t'][mask];q=z['q'][mask];v=z['v'][mask];a=z['a'][mask]
  dt=np.diff(t);dq=np.diff(q,axis=0)/dt[:,None];mean_v=(v[:-1]+v[1:])/2;diff=dq-mean_v
  still=(np.max(np.abs(np.diff(q,axis=0)),axis=1)<1e-12)&(np.max(np.abs(mean_v),axis=1)>1e-4)
  ids=np.flatnonzero(still);example=None
  if len(ids):
   i=int(ids[0]);example=dict(t=t[i:i+2],q=q[i:i+2],dq_declared=v[i:i+2],ddq_declared=a[i:i+2],q_finite_difference=dq[i])
  rows.append(dict(phase=phase,constant_q_nonzero_declared_dq_intervals=int(np.sum(still)),max_q_derivative_vs_declared_dq_mismatch=float(np.max(np.abs(diff))),declared_acceleration_peak=np.max(np.abs(a),axis=0),example=example))
 old=read('B_tape_replay_interface.json')['records'][0]['certificate']
 save('REFERENCE_RECONSTRUCTION_DIAGNOSIS.json',dict(rows=rows,rejected_first_phase_derivatives=old['derivatives'],finding='A q/dq/ddq intent tuple logged during B planning waits is not a phase-clock C2 spline sample. Quintic interpolation of that tuple invents large intra-cell acceleration and jerk. This is a failed research representation, not evidence of a measured Human safety violation or authority to change B.',required_resolution='A residual realization must retain native B schedule/governor/wait ownership and its exact clock semantics; sampled tuple interpolation is not promotable.',B_unchanged=True,thresholds_unchanged=True))
 print(json.dumps(clean(rows)),flush=True)
if __name__=='__main__':main()
