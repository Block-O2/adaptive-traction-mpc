"""Independent saved-raw branch, receipt and native-motion audit; no physics stepping."""
import os,sys,json,gzip,hashlib,time
from pathlib import Path
from types import SimpleNamespace
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');sys.dont_write_bytecode=True
P=Path(__file__).resolve().parents[1];R=P/'runtime';O=Path('/home/hank/ihear-lab/autonomous_coordination_learning_v2')
sys.path[:0]=[str(R/'control'),str(R/'code')]
import study_common as sc
import numpy as np
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.high_rom_v1 import deployable_prior
from traction_mpc_stage3.coupled import BED_HEIGHT_M,SLEEVE_HALF_LENGTH_M,SLEEVE_OUTER_RADIUS_M
from traction_mpc_stage5.full3d_adaptive_integration_v1.rigid_table_reference import RigidTableReferenceEnvelopeV1
from traction_mpc_stage5.full3d_adaptive_integration_v1.clearance_feedback import clearance_acceleration_correction

def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def put(n,v):
 f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(sc.clean(v),indent=2,ensure_ascii=False,allow_nan=False)+'\n')

def analyze(ident,root=O):
 path=root/'runtime/source/results'/ident
 with gzip.open(path/'runtime_artifacts.json.gz','rt') as f:raw=json.load(f)
 m=json.loads((root/'runtime/reports'/(ident+'_MEASURED.json')).read_text());native=raw['wall_physics']['native_states_evaluation_only'];receipts=raw['wall_physics']['command_receipts'];events=[e for e in raw['execution_attempts'] if e.get('clearance_feedback')]
 e=min(events,key=lambda e:e['clearance_feedback']['model_curvature_m_s2']);c=e['clearance_feedback'];when=e['source_sample_time_s'];receipt=min(receipts,key=lambda r:abs(r['source_sample_time_s']-when));state=np.array(receipt['validation_state']);q,dq=state[:2],state[2:]
 with np.load(path/'trace.npz') as z:
  task=z['stage']=='TASK';tt=z['time_s'][task];f=z['physical_cuff_force_world_n'][task];mm=z['physical_cuff_moment_world_nm'][task];JF=float(np.linalg.norm(f[:-1],axis=1)@np.diff(tt));JM=float(np.linalg.norm(mm[:-1],axis=1)@np.diff(tt))
 t=np.array([n['time_s'] for n in native]);use=(t>=tt[0]-1e-9)&(t<=tt[-1]+1e-9);t=t[use];qi=m['quality']['qpos_indices'];vi=m['quality']['qvel_indices'];v=np.array([n['qvel_evaluation_only'] for n in native])[use][:,vi];qtrue=np.array([n['qpos_evaluation_only'] for n in native])[use][:,qi];a=np.gradient(v,t,axis=0,edge_order=2);j=np.gradient(a,t,axis=0,edge_order=2)
 join=[n for n in native if e['start_physics_s']+1e-10<n['time_s']<=e['end_physics_s']+1e-10];tau=np.array(receipt['command_torque_nm']);identity=len(join)==receipt['native_steps'] and e['applied_robot_tau_nm']==receipt['command_torque_nm'] and all(n['command_torque_nm']==receipt['command_torque_nm'] for n in join)
 previous=max((r for r in receipts if r['start_physics_s']<when-1e-9),key=lambda r:r['start_physics_s']);window=(t>=when-.02)&(t<=when+.025);window_events=[z for z in events if abs(z['source_sample_time_s']-when)<=.02];window_receipts=[r for r in receipts if abs(r['source_sample_time_s']-when)<=.02]
 # Count crossed finite-difference endpoint stencils using the receipt-owned estimated state.
 rmap={round(r['source_sample_time_s'],7):r for r in receipts};cross=[]
 for ev in events:
  r=rmap.get(round(ev['source_sample_time_s'],7))
  if r is None or 'validation_state' not in r:continue
  ss=np.array(r['validation_state']);phi=ss[0]-ss[1];rate=ss[2]-ss[3]
  if np.sin(phi-1e-5*rate)*np.sin(phi+1e-5*rate)<0:cross.append({'time_s':ev['source_sample_time_s'],'curvature':ev['clearance_feedback']['model_curvature_m_s2'],'correction_nm':ev['clearance_feedback']['correction_nm']})
 metrics={'id':ident,'source_root':str(root),'JF_independent':JF,'JM_independent':JM,'JF_error':JF-m['J_F_N_s'],'JM_error':JM-m['moment_integral_Nm_s'],'axes':m['axes'],'clearance':m['clearance'],'min_curvature_m_s2':c['model_curvature_m_s2'],'event_time_s':when,'event_state':state,'model_axis_z':float(np.sin(q[0]-q[1])),'model_axis_rate':float(np.cos(q[0]-q[1])*(dq[0]-dq[1])),'stencil_crossing_events':cross,'guard':c,'event_generalized_action_nm':e.get('generalized_action_nm'),'accepted_receipt_torque_nm':tau,'previous_receipt_torque_nm':previous['command_torque_nm'],'torque_delta_nm':tau-np.array(previous['command_torque_nm']),'native_receipt_join_pass':identity,'native_rows_in_receipt':len(join),'native_acceleration_max_deg_s2':np.max(abs(np.degrees(a)),axis=0),'native_jerk_RMS_deg_s3':np.sqrt(np.mean(np.degrees(j)**2,axis=0)),'native_jerk_peak_deg_s3':np.max(abs(np.degrees(j)),axis=0),'native_jerk_peak_times_s':[t[np.argmax(abs(j[:,k]))] for k in range(2)],'window_native_jerk_peak_deg_s3':np.max(abs(np.degrees(j[window])),axis=0),'window_events':window_events,'window_receipts':window_receipts,'raw_identity':{str(path/x):sha(path/x) for x in ['trace.npz','summary.json','runtime_artifacts.json.gz']},'limitations':['Native acceleration/jerk reconstructed by original unfiltered gradient convention. They are not the guard model curvature.','Pre-guard six-axis robot requested torque is not separately recorded; generalized command and applied robot torque have different dimensions.']}
 put('analysis/forensics/'+ident+'.json',metrics);np.savez_compressed(P/'analysis/forensics'/(ident+'_window.npz'),t=t[window],q=qtrue[window],v=v[window],a=a[window],j=j[window]);print(ident,'curv',c['model_curvature_m_s2'],'cross',len(cross),'join',identity,'JF',JF,flush=True)
 return metrics

def diagnostic(ident):
 inp=json.loads((P/'analysis/forensics'/(ident+'.json')).read_text());c=inp['guard'];state=np.array(inp['event_state']);b=json.loads((O/'history/CAUSAL_COMMISSIONED_BELIEF.json').read_text());g=PlanarCuffGeometry(**{k:np.array(v) if isinstance(v,list) else v for k,v in b['geometry'].items()});model=sc.rt.StateResidualHumanModel(g,np.array(b['beta']),deployable_prior(),residual_weights_nm=np.array(b['residual_weights_nm']));env=RigidTableReferenceEnvelopeV1(g)
 # Scalar-sufficient adapter: original guard consumes causal pose/twist only via gap and gap velocity.
 interface=SimpleNamespace(human_position_world_m=np.array([0.,0.,c['gap_m']+SLEEVE_OUTER_RADIUS_M+BED_HEIGHT_M]),human_rotation_world=np.eye(3),human_velocity_world_m_s=np.array([0.,0.,c['gap_velocity_m_s']]),human_angular_velocity_world_rad_s=np.zeros(3))
 rows=[]
 for delta in [-1e-4,-1e-5,-3e-6,-1e-6,-3e-7,0.,3e-7,1e-6,3e-6,1e-5,1e-4]:
  ss=state.copy();ss[0]+=delta;corr,rec=clearance_acceleration_correction(model,ss,np.array(c['requested_acceleration_rad_s2']),interface,np.array(c['joint_acceleration_box_rad_s2']),response_s=c['response_s'],adverse_acceleration_m_s2=c['adverse_acceleration_m_s2']);rows.append({'delta_hip_rad':delta,'guard':rec})
 zero=rows[5]['guard'];errors={k:float(np.max(abs(np.array(zero[k])-np.array(c[k])))) for k in ['model_curvature_m_s2','model_gap_gradient_m_rad','correction_nm','required_gap_acceleration_m_s2']}
 # Algebraically identical endpoint expressions: equal geometry floor only, no alternative controller or safety qualification.
 qr=state[:2];vr=state[2:];branch=[]
 for h in [1e-3,1e-4,1e-5,1e-6,1e-7]:
  vals=[]
  for q in [qr-h*vr,qr,qr+h*vr]:
   az=np.sin(q[0]-q[1]);smooth=float(env.cuff_centers(q)[0,2]-SLEEVE_OUTER_RADIUS_M*np.sqrt(1-az*az)-BED_HEIGHT_M);vals.append((smooth-SLEEVE_HALF_LENGTH_M*az,smooth+SLEEVE_HALF_LENGTH_M*az))
  vals=np.array(vals);endpoint_curv=(vals[0]-2*vals[1]+vals[2])/(h*h);envelope_curv=(vals[0].min()-2*vals[1].min()+vals[2].min())/(h*h);branch.append({'h_s':h,'endpoint_curvatures_m_s2':endpoint_curv,'minimum_curvature_m_s2':envelope_curv,'gap_min_equivalence_error_m':float(vals[1].min()-env.margins(qr)['sleeve_m'][0])})
 put('analysis/forensics/'+ident+'_diagnostic.json',{'original_guard_replay_errors':errors,'q_only_sensitivity':rows,'endpoint_decomposition':branch,'new_native_steps':0,'adapter':'Exact recorded gap and gap-rate sufficient scalars, synthetic pose/twist representation; not a physical state reconstruction.','experimental_guard_physics':'NOT_RUN','replacement_safety_qualification':'NOT_TESTED'})
 print(ident,'replay_errors',errors,flush=True)
if __name__=='__main__':
 ids=sys.argv[1:] or ['CORE_C_019','PPO_SCRATCH_TRAIN_0009','MOTION_CAUSE_TIME_PLUS_010']
 for ident in ids:
  root=P if (R/'source/results'/ident).exists() else O;analyze(ident,root)
  if ident in ['CORE_C_019','PPO_SCRATCH_TRAIN_0009']:diagnostic(ident)
