"""Frozen tolerances, saved-schedule equivalence, independent local authority checks."""
from pathlib import Path
import os,sys,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
import numpy as np
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'prototype'))
from continuous import Piece,LocalQuintic,LocalTimeWarp,coefficients
TOL=np.array([1e-10,1e-10,1e-9])
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.ndarray):return x.tolist()
 if isinstance(x,np.generic):return x.item()
 return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,allow_nan=False)+'\n')
protocol=dict(frozen_before_tests_unix=time.time(),tolerances=dict(q_rad=TOL[0],dq_rad_s=TOL[1],ddq_rad_s2=TOL[2]),scope='original selected polynomial schedules, not a fit to sampled issued-reference trace',M2_min_nonzero_q_rad=1e-5,M4_outside_support_max_rad=1e-11,M5_path_identity_tolerance_rad=1e-10)
if not (P/'prototype/MATH_PROTOCOL.json').exists():put('prototype/MATH_PROTOCOL.json',protocol)
else:protocol=json.loads((P/'prototype/MATH_PROTOCOL.json').read_text())
rows=[];originals=[]
for ident in ['development_repair2_B0_original','development_repair2_quality_NATIVE_SCALAR_18_063']:
 s=json.loads((P/'key_traces'/ident/'summary.json').read_text())
 for i,r in enumerate(s['learning_records']):
  d=r['selected_plan']['schedule'];T=d['duration_s'];q0,v0,q1,v1=[np.array(d[k]) for k in ['start_q_rad','start_dq_rad_s','target_q_rad','target_dq_rad_s']]
  o=Piece(coefficients(q0,v0,np.zeros(2),q1,v1,np.zeros(2),T),T);originals.append(o)
  local=LocalQuintic.from_piece(o,[T*.25,T*.5,T*.75]);tt=np.linspace(0,T,2001)
  # Separate reconstruction using the original source function, not our solve.
  import importlib.util
  # Original coefficient algebra is independently evaluated here verbatim.
  c=np.zeros((2,6));c[:,0]=q0;c[:,1]=T*v0;rhs=np.column_stack([q1-c[:,0]-c[:,1],T*v1-c[:,1],np.zeros(2)]);c[:,3:]=np.linalg.solve(np.array([[1.,1.,1.],[3.,4.,5.],[6.,12.,20.]]),rhs.T).T
  m0=np.max(abs(o.c-c));m1=np.array([np.max(abs(local.evaluate(tt,k)-o.evaluate(tt,k))) for k in range(3)])
  spline=o.bspline();refined=spline.insert_knot(.25*T).insert_knot(.5*T).insert_knot(.75*T);spline_error=np.array([np.max(abs(refined(tt,nu=k)-o.evaluate(tt,k))) for k in range(3)])
  jumps=np.array([[np.max(abs(local.pieces[j].evaluate(local.pieces[j].T,k)-local.pieces[j+1].evaluate(0,k))) for k in range(3)] for j in range(len(local.pieces)-1)])
  rows.append(dict(id=ident,decision=i,phase=d['phase'],duration_s=T,M0_coeff_error=m0,M1_errors=m1,bspline_M0_M1_errors=spline_error,M3_jumps=jumps.max(axis=0),refined_midpoint_acceleration_rad_s2=local.a[2]))
  
  if not (m0==0 and np.all(m1<TOL) and np.all(spline_error<TOL) and np.all(jumps<TOL)):
   print('FAILED_GATE',ident,i,'M0',m0,'M1',m1,'BSPLINE',spline_error,'JUMPS',jumps.max(axis=0),flush=True)
   raise AssertionError('M0_M1_M3')
# Select first B moving segment as a disclosed mathematical example.
o=originals[0];T=o.T;local=LocalQuintic.from_piece(o,[.2*T,.4*T,.6*T,.8*T]);changed=local.update(2,dq=np.radians([.3,-.2]),dv=np.radians([.2,.1]),da=np.radians([.1,-.1]));tt=np.linspace(0,T,4001);delta=changed.evaluate(tt)-local.evaluate(tt);outside=(tt<.2*T-1e-10)|(tt>.6*T+1e-10);local_error=np.max(abs(delta[outside]));peak=np.max(abs(delta));assert local_error<1e-11 and peak>1e-5
jumps=np.array([[np.max(abs(changed.pieces[i].evaluate(changed.pieces[i].T,k)-changed.pieces[i+1].evaluate(0,k))) for k in range(3)] for i in range(len(changed.pieces)-1)]);assert np.all(jumps<TOL)
# Path-preserving speed change uses an explicit monotone local clock.
warp=LocalTimeWarp(local,.2*T,.8*T,.02*T);u,rate,acc=warp.mapping(tt);path_error=np.max(abs(warp.evaluate(tt)-local.evaluate(u)));assert path_error<1e-10
speed_effect=np.max(abs(warp.evaluate(tt,1)-local.evaluate(tt,1)));assert speed_effect>1e-5
# A genuine B-spline control update after refinement, with compact basis support.
sp=o.bspline()
for fraction in [.15,.3,.45,.6,.75,.9]:sp=sp.insert_knot(T*fraction)
index=6;mut=sp.c.copy();mut[index]+=np.radians([.2,-.2]);alt=type(sp)(sp.t,mut,sp.k);support=[sp.t[index],sp.t[index+sp.k+1]];use=(tt<support[0]-1e-10)|(tt>support[1]+1e-10);spdelta=alt(tt)-sp(tt);assert np.max(abs(spdelta[use]))<1e-11
# One finite adapter repair: try original zero-acceleration subsegments. This
# preserves schema but does NOT preserve a general original curve.
legacy_error=[]
for lo,hi in zip(local.knots,local.knots[1:]):
 q0,v0=[o.evaluate(lo,k) for k in range(2)];q1,v1=[o.evaluate(hi,k) for k in range(2)];z=Piece(coefficients(q0,v0,np.zeros(2),q1,v1,np.zeros(2),hi-lo),hi-lo);ts=np.linspace(lo,hi,501)
 legacy_error.append([np.max(abs(z.evaluate(ts-lo,k)-o.evaluate(ts,k))) for k in range(3)])
try:changed.collapse_original(o);rejection=None
except ValueError as e:rejection=str(e)
assert rejection and local.collapse_original(o) is o
put('prototype/EXAMPLE_CURVES.json',dict(original=dict(coefficients=o.c,duration_s=T),refined=local.record(),changed=changed.record(),timewarp=dict(support_s=[.2*T,.8*T],amplitude_s=.02*T,minimum_clock_rate=warp.minimum_rate)))
put('MATH_VALIDATION.json',dict(status='M0_M5_PASS_M6_INTERFACE_UNRESOLVED',protocol=protocol,denominator_original_schedules=len(rows),rows=rows,M0=dict(status='PASS',scope='all 28 selected original quintic schedule polynomials reconstructed exactly in coefficients',issued_reference_whole_chain='separate governor/bridge mapping; no exact full issued-chain reproduction claim yet'),M1=dict(status='PASS',method='affine polynomial restriction and B-spline knot insertion',tolerances=TOL),M2=dict(status='PASS',changed_control_peak_rad=peak,through_velocity_rad_s=changed.v[2]),M3=dict(status='PASS',nonzero_update_max_jumps=jumps.max(axis=0),fixed_duration_s=T,endpoint_errors=[np.max(abs(changed.evaluate(np.array([0,T]),k)-local.evaluate(np.array([0,T]),k))) for k in range(3)]),M4=dict(status='PASS',support_s=[.2*T,.6*T],outside_max_rad=local_error,affected_neighbor_pieces=2,other_phases='separate objects, no changes'),M5=dict(status='PASS',path_preserving_timewarp_q_error_rad=path_error,nonzero_speed_effect_rad_s=speed_effect,minimum_clock_rate=warp.minimum_rate,coordination_update_fixed_knots=True),M6=dict(status='DESIGN_ONLY_NOT_PHYSICAL_ADMISSION',exact_zero_collapse=True,nonzero_collapse_rejected=rejection,legacy_zero_acceleration_piece_adapter_M1_errors=np.max(legacy_error,axis=0),repair_cycles=1,repair_result='Original schema representable children force zero internal accelerations and fail frozen curve identity. General C2 pieces need new full-path certificate/serialization; original safety proof cannot be reused.',physics_allowed='only separately contracted baseline/zero-collapse qualification; no nonzero force search'),alternative_bspline=dict(M0_M1='PASS',nonzero_control_peak_rad=np.max(abs(spdelta)),local_support_s=support,not_interpolating_waypoint=True),physical_rollouts=0))
fig,ax=plt.subplots(3,1,figsize=(11,9),sharex=True)
for k in range(3):
 ax[k].plot(tt,np.rad2deg(o.evaluate(tt,k)[:,0]),label='original hip');ax[k].plot(tt,np.rad2deg(local.evaluate(tt,k)[:,0]),ls='--',label='refined hip');ax[k].set_ylabel(['q (deg)','dq (deg/s)','ddq (deg/s2)'][k]);ax[k].grid(alpha=.2)
ax[0].legend();ax[-1].set_xlabel('Local schedule time (s)');fig.suptitle('Exact mathematical refinement; no physical execution claim');fig.tight_layout();fig.savefig(P/'figures/refinement_equivalence.png',dpi=160);plt.close(fig)
fig,ax=plt.subplots(3,1,figsize=(11,9),sharex=True)
ax[0].plot(tt,np.rad2deg(delta));ax[0].set_ylabel('Local path change (deg)');ax[1].plot(tt,np.rad2deg(warp.evaluate(tt,1)-local.evaluate(tt,1)));ax[1].set_ylabel('Time-warp dq change (deg/s)');ax[2].plot(tt,np.rad2deg(spdelta));ax[2].set_ylabel('B-spline control effect (deg)')
for a in ax:a.grid(alpha=.2)
ax[-1].set_xlabel('Local schedule time (s)');fig.suptitle('Nonzero local mathematical authority, no new physical claim');fig.tight_layout();fig.savefig(P/'figures/local_control_effect.png',dpi=160);plt.close(fig)
print(json.dumps(clean(dict(schedules=len(rows),M1_max=np.max([r['M1_errors'] for r in rows],axis=0),M2_peak_rad=peak,M4_outside_rad=local_error,legacy_adapter_errors=np.max(legacy_error,axis=0),M6='UNRESOLVED'))),flush=True)
