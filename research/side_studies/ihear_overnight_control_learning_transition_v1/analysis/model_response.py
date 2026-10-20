"""Causal origin-frozen 2DOF model validation; never steps MuJoCo or reads future inputs."""
from pathlib import Path
import os,sys,json,time,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
for stage in ['stage2_linkage','stage3_full3d','stage4_adaptive_control','stage5_personalized_motion_learning']:sys.path.insert(0,str(P/'source/stages'/stage/'src'))
sys.path.insert(0,str(P/'deps'))
import numpy as np
from traction_mpc_stage4.estimator_v2 import PlanarCuffGeometry
from traction_mpc_stage5.architecture_recovery_v2.functional_benchmark import StateResidualHumanModel
from traction_mpc_stage5.high_rom_v1 import deployable_prior
A=P.parent/'ihear_model_terminal_compensation_v1'
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    return x
def put(n,x):(P/n).write_text(json.dumps(clean(x),indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def stats(e):return dict(rmse=np.sqrt(np.mean(e*e,axis=0)),p95_abs=np.quantile(abs(e),.95,axis=0),max_abs=np.max(abs(e),axis=0),bias=e.mean(0))
cases=[(A,'Ctrl_ER'),(A,'Ctrl_H150'),(A,'W2_ER'),(A,'W2_H150')]+[(P,g+'_H150') for g in sys.argv[1:]]
summary=[];instant=[];sources={};geometry_lineage=[]
for root,ident in cases:
    folder=root/'source/results'/ident
    z=np.load(folder/'trace.npz');mask=z['stage']=='TASK';t=z['time_s'][mask];rel=t-t[0]
    x=z['estimated_human_state_rad_rad_s'][mask];y=z['evaluation_only_human_state_rad_rad_s'][mask]
    beta=z['task_beta'];weights=z['task_residual_weights_nm'];f=z['physical_cuff_force_world_n'][mask];m=z['physical_cuff_moment_world_nm'][mask];u=z['applied_generalized_action_nm'][mask]
    rq=z['reference_q_rad'][mask];rv=z['reference_dq_rad_s'][mask]
    # task_beta/task_residual rows are TASK-only in this archived schema, as prior audited analysis.
    assert len(beta)==len(x) and len(weights)==len(x)
    su=json.loads((folder/'summary.json').read_text());records=su['learning_records'];g=records[0]['adaptive_state']['effective_geometry'];geo=PlanarCuffGeometry(**{k:np.array(v) if isinstance(v,list) else v for k,v in g.items()})
    assert all(r['adaptive_state']['effective_geometry']==g for r in records),'GEOMETRY_NOT_CONSTANT_WITHIN_TASK'
    native=np.load(root/'motion_series'/(ident+'.npz'));na=np.column_stack([np.interp(t,native['time_s'],native['acceleration_rad_s2'][:,j]) for j in range(2)])
    errors={};origins=np.arange(20,len(t)-41,10);origins=origins[(rel[origins]>=15.3)&(rel[origins]<=17.6)]
    assert records[0]['request_time_s']<float(t[origins].min())
    assert records[0]['adaptive_state']['deployable_truth_consumed'] is False
    geometry_lineage.append(dict(id=ident,source='first request adaptive_state effective_geometry',source_physical_s=records[0]['request_time_s'],first_prediction_origin_physical_s=float(t[origins].min()),all_task_requests_same_geometry=True,source_precedes_every_origin=True,truth_consumed=False))
    for i in origins:
        model=StateResidualHumanModel(geometry=geo,beta=beta[i],rom_human=deployable_prior(),residual_weights_nm=weights[i],residual_limit_nm=12.)
        sensed=geo.generalized_input_from_wrench(x[i,:2],f[i],m[i]);am=model.continuous_dynamics(x[i],sensed)[2:];au=model.continuous_dynamics(x[i],u[i])[2:]
        pd=(rq[i]-x[i,:2])*[180,140]+(rv[i]-x[i,2:])*[28,22]
        instant.append(dict(id=ident,task_s=rel[i],PD_request_deg_s2=np.rad2deg(pd),requested_model_deg_s2=np.rad2deg(au),sensed_wrench_model_deg_s2=np.rad2deg(am),native_actual_deg_s2=np.rad2deg(na[i])))
        states={k:x[i].copy() for k in ['held_measured_wrench','held_requested_generalized_action']}
        for step in range(1,41):
            for key,state in states.items():
                inp=geo.generalized_input_from_wrench(state[:2],f[i],m[i]) if key=='held_measured_wrench' else u[i]
                states[key]=model.step_dynamics(state,inp,.005)
            if step in [20,40]:
                for key,state in states.items():errors.setdefault((key,step),[]).append(np.rad2deg(state-y[i+step]))
    for (key,step),e in errors.items():summary.append(dict(id=ident,method=key,horizon_s=step*.005,region='terminal',n=len(e),**stats(np.array(e))))
    sources[str(folder/'trace.npz')]=hashlib.sha256((folder/'trace.npz').read_bytes()).hexdigest()
    print('MODEL_RESPONSE_DONE',ident,flush=True)
put('derived/COUPLED_MODEL_PREDICTION.json',dict(status='COMPLETED',rows=summary,instantaneous_rows=instant,sources=sources,geometry_lineage=geometry_lineage,new_physics_starts=0,truth_only_evaluation=True,inputs_frozen_at_origin=True,predicts_robot_controller=False,predicts_hypothetical_action_cost=False,precision_not_certified=True))
