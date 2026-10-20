"""No-physics observer raw-copy edge cases against the original real formulas."""
from task_bootstrap import *
def main():
 import study_common,numpy as np,deferred_evaluation as d
 from types import SimpleNamespace as NS
 d.install()
 from traction_mpc_stage5.full3d_adaptive_integration_v1.fast_physics_monitor import FastTruePhysicsMonitor as C
 reference=C();deferred=C();model=NS(geom=lambda name:NS(id=0),geom_size=np.asarray([[.04,.25,0.],[0.,0.,0.]]));data=NS(geom_xpos=np.zeros((2,3)),geom_xmat=np.zeros((2,9)),qpos=np.zeros(2),ncon=0,contact=[]);human=NS(q_min_rad=np.asarray([0.,0.]),q_max_rad=np.asarray([2.,2.]));plant=NS(model=model,data=data,human=human,human_qpos_indices=np.asarray([0,1]),bed_geom_id=1,_interface_value=NS(human_wrench_world=np.zeros(6)))
 cases=[('COMMISSIONING',True,.4,1.,[.1,.2],[3.,4.,0.,0.,0.,2.],False),('COMMISSIONING',False,.38,-.5,[-.01,.2],[0.,0.,0.,1.,2.,2.],True),('ACTIVE_RECOVERY',True,.31,.9,[.2,2.01],None,False),('TASK',False,.5,.2,[.5,.8],[1.,2.,3.],False),('TASK',True,.35,-.8,[.8,.9],[float('nan'),0.,0.,0.,0.,0.],True),('TASK',True,.27,1.,[.7,.5],[1.,2.,2.,0.,3.,4.],False)]
 for stage,integrated,z,axis,q,wrench,touch in cases:
  data.geom_xpos[0,2]=z;data.geom_xpos[1,2]=.01;data.geom_xmat[0,8]=axis;data.qpos[:]=q;data.ncon=int(touch);data.contact=[NS(geom1=0,geom2=1)] if touch else [];plant._interface_value.human_wrench_world=None if wrench is None else np.asarray(wrench)
  reference.stage=deferred.stage=stage;d.ORIGINAL_OBSERVE(reference,plant,integrated_step=integrated);deferred.observe(plant,integrated_step=integrated)
 expected=d.ORIGINAL_RECORD(reference);actual=deferred.record();assert expected==actual,'DEFERRED_ORIGINAL_FORMULA_DIFFERENCE';assert deferred.record()==actual,'DEFERRED_RECORD_NOT_IDEMPOTENT';assert len(deferred._deferred_rows)==0
 out=dict(status='PASS',samples=6,physics_added=0,real_original_observe_formula=True,original_record_bit_exact=True,edge_cases=['phase ownership','native/boundary count','shank/bed contact','ROM bound violation','missing/malformed/nonfinite cached wrench','original sqrt finite wrench','record idempotence'],synthetic_observer_inputs_only=True,not_actual_physical_execution=True)
 save(STUDY/'reports/DEFERRED_EVALUATION_CONTRACT_CHECK.json',out);print(json.dumps(out))
if __name__=='__main__':main()
