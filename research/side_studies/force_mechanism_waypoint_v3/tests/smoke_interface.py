from fixture import *
import pickle
from traction_mpc_stage5.full3d_adaptive_integration_v1.multisegment_reference import *
from traction_mpc_stage5.full3d_adaptive_integration_v1.activation_validation import validate_activation
f=fixture()
for amplitude in [0.,.05]:
 intent={**f['context'],'perturbation_deg':[0.,amplitude]}
 d=adapt_decision(f['decision'],f['planner'],f['belief'],intent);s=d.executed.schedule
 s2=pickle.loads(pickle.dumps(s,protocol=5));s2.assert_integrity()
 first=s.sample(0.);r=validate_activation(belief=f['belief'],request_sequence=f['belief'].sequence,schedule=s,clearance=f['clearance'],phase=TaskPhase.OUTBOUND,request_phase=TaskPhase.OUTBOUND,remaining_s=8.,reference_state=np.r_[first.q_rad,first.dq_rad_s],now_physics_s=f['context']['source_sample_time_s']+.005)
 print('SMOKE',amplitude,s.sealed_digest,s.certificate['feasible'],r['feasible'],len(encode(s)),flush=True)
 assert r['feasible']
