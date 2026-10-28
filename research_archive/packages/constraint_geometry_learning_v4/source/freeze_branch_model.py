from pathlib import Path
import sys,os,json,gzip,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'source'),str(P/'runtime/control'),str(P/'runtime/code')]
from acl2_shared import put,sha,utc
import numpy as np
from endpoint_study import endpoints,MODEL,L,RAD,BED_HEIGHT_M,clearance_acceleration_correction
from types import SimpleNamespace
O=P.parent/'representation_execution_v3';training=[];when=27.07000000003824;causal=[]
for tag,delta in [('C19',0.),('C19_DM0p0010',-.001),('C19_DM0p0001',-.0001),('C19_DP0p0001',.0001),('C19_DP0p0010',.001)]:
 f=O/'runtime/source/results'/('P2_'+tag)/'runtime_artifacts.json.gz'
 with gzip.open(f,'rt') as z:d=json.load(z)
 r=min(d['wall_physics']['command_receipts'],key=lambda r:abs(r['source_sample_time_s']-when));ss=np.array(r['validation_state']);ev=min((e for e in d['execution_attempts'] if e.get('clearance_feedback')),key=lambda e:abs(e['source_sample_time_s']-when));c=ev['clearance_feedback'];assert abs(r['source_sample_time_s']-when)<1e-8
 training.append(dict(id='P2_'+tag,delta=delta,phi=float(ss[0]-ss[1]),relative_rate=float(ss[2]-ss[3]),curvature=c['model_curvature_m_s2'],qualified=json.loads((O/'attempts'/('P2_'+tag+'_RESULT.json')).read_text())['qualified'],raw_sha256=sha(f),feature_source='candidate delta and historical causal estimated state; no Human truth'))
 if delta==0:
  tr=min(d['trace'],key=lambda r:abs(r['time_s']-when));assert abs(tr['time_s']-when)<1e-8
  it=SimpleNamespace(human_position_world_m=np.array(tr['cuff_position_world_m']),human_rotation_world=np.array(tr['cuff_rotation_world']),human_velocity_world_m_s=np.array(tr['cuff_linear_velocity_world_m_s']),human_angular_velocity_world_rad_s=np.array(tr['cuff_angular_velocity_world_rad_s']))
  corr,rep=clearance_acceleration_correction(MODEL,ss,np.array(c['requested_acceleration_rad_s2']),it,np.array(c['joint_acceleration_box_rad_s2']),response_s=c['response_s'],adverse_acceleration_m_s2=c['adverse_acceleration_m_s2'])
  axis=it.human_rotation_world[:,0];az=float(axis[2]);adot=float(np.cross(it.human_angular_velocity_world_rad_s,axis)[2]);root=np.sqrt(1-az*az);z=it.human_position_world_m[2];vz=it.human_velocity_world_m_s[2];ep=endpoints(ss[:2],ss[2:]);measured=[dict(gap=z+s*L*az-RAD*root-BED_HEIGHT_M,velocity=vz+(s*L+RAD*az/root)*adot) for s in [-1,1]]
  from traction_mpc_stage5.full3d_adaptive_integration_v1.clearance_feedback import project_acceleration_halfspaces
  req=np.array([2*(1e-5-m['gap']-c['response_s']*m['velocity'])/c['response_s']**2+c['adverse_acceleration_m_s2'] for m in measured]);A=np.array([e['gradient'] for e in ep]);cur=np.array([e['curvature'] for e in ep]);adj,feas=project_acceleration_halfspaces(c['requested_acceleration_rad_s2'],A,req-cur,np.array(c['joint_acceleration_box_rad_s2']))
  causal=dict(id='P2_C19',source_time_s=when,source='same-time archived measured trace; replay residual explicitly checked',measured_axis_z=az,model_axis_z=np.sin(ss[0]-ss[1]),measured_axis_rate=adot,model_axis_rate=np.cos(ss[0]-ss[1])*(ss[2]-ss[3]),original_replay_errors={k:float(np.max(abs(np.asarray(rep[k])-np.asarray(c[k])))) for k in ['gap_m','gap_velocity_m_s','correction_nm']},measured_endpoint_gaps_and_rates=measured,model_endpoint_derivatives=ep,dual_required=req,dual_adjusted_acceleration=adj,dual_box_feasible=feas,physical_execution='NOT_RUN',protection_qualification='NOT_ESTABLISHED')
 del d
x=np.array([r['delta'] for r in training]);X=np.c_[np.ones(len(x)),x];y=np.array([[r['phi'],r['relative_rate']] for r in training]);coef=np.linalg.lstsq(X,y,rcond=None)[0];res=y-X@coef;loo=[]
for i in range(len(x)):
 keep=np.arange(len(x))!=i;cc=np.linalg.lstsq(X[keep],y[keep],rcond=None)[0];loo.append((y[i]-X[i]@cc).tolist())
model=dict(schema='v4.local_causal_branch_affine.v1',frozen_utc=utc(),training=training,coefficients=coef.tolist(),outputs=['phi_at_27p07','relative_rate_at_27p07'],domain={'candidate':'C19 x[3] only','delta':[-.001,.001],'condition':'historical D01 W1 full causal parent'},h_s=1e-5,L_m=L,severe_curvature_threshold_m_s2=-50.,fit_max_abs_errors=np.max(abs(res),axis=0).tolist(),LOO_max_abs_errors=np.max(abs(np.asarray(loo)),axis=0).tolist(),limits=['fixed event cell; no extrapolation to other phases, parameters, prefix or Human','motion risk proxy, not original full-motion certificate','training labels include historical physical outcomes; all candidate predictions precede new physical outcomes'])
put('analysis/FROZEN_BRANCH_MODEL.json',model);put('analysis/CAUSAL_ENDPOINT_REPLAY.json',causal)
cfg=json.loads((P/'experiments/DEV.json').read_text())
for a in cfg['actions']:
 if a['tag']=='C19' or 'local_delta' in a:
  delta=a.get('local_delta',0.);phi,rate=np.array([1.,delta])@coef;curve=-2*L*max(0.,1e-5*abs(rate)-abs(phi))/1e-10;a['prediction']=dict(type='frozen_traditional_branch_model',model_sha256=sha(P/'analysis/FROZEN_BRANCH_MODEL.json'),delta=delta,predicted_phi=phi,predicted_rate=rate,predicted_curvature_spike=curve,predicted_severe_guard_impulse=bool(curve< -50.),predicted_motion_pass=bool(curve>=-50.),truth_input=False)
 else:a['prediction']=dict(type='ABSTAIN_OUT_OF_LOCAL_MODEL_DOMAIN',truth_input=False)
put('predictions/DEV_PREREGISTERED_PREDICTIONS.json',dict(frozen_utc=utc(),actions=cfg['actions'],scope='Created before any unseen local candidate START; worker config remains frozen'))
print('MODEL',json.dumps(model,ensure_ascii=False));print('PREDICTIONS',[(a['tag'],a['prediction']) for a in cfg['actions']]);print('EXACT_CAUSAL_REPLAY',causal['original_replay_errors'],'MEASURED_MODEL_AZ',causal['measured_axis_z'],causal['model_axis_z'])
