"""Current saved-state linear-Q contribution audit; no fit or physics."""
from task_bootstrap import *
import pickle,numpy as np
def main():
 import native_core as nc
 from native_inference import Networks
 net=Networks(STUDY/'weights/frozen_Q_v1');assert net.meta['selected_Q']=='linear';coef=np.asarray(net.w['linear_W'],np.float64)/net.w['x_scale']*net.w['y_scale'];offset=float(net.w['y_mean']+net.w['y_scale']*net.w['linear_b']-coef@net.w['x_mean'])
 paths=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));assert len(paths)==22;rows=[];probes=[]
 for p in paths:
  raw=pickle.loads(p.read_bytes());c=raw['context'];count=raw['count'];carry=raw['carry'];pool=nc.candidates(c,count,carry,2621,6);x=np.asarray([nc.feature(c,plan,count,carry) for plan,source in pool]);native=net.values(x);real=x.astype(np.float64)@coef+offset
  contributions={key:(x[:,a:b].astype(np.float64)@coef[a:b]).tolist() for key,a,b in [('state',0,58),('U',58,88),('carry',88,118),('issued',118,120)]};deltaerr=float(max(abs((native[i]-native[j])-(real[i]-real[j])) for i in range(len(pool)) for j in range(len(pool))))
  assert all(np.array_equal(x[:,a:b],np.broadcast_to(x[0,a:b],x[:,a:b].shape)) for a,b in ((0,58),(88,118),(118,120))),'CANDIDATE_INDEPENDENT_FEATURE_CHANGED'
  rows.append(dict(snapshot=str(p),state_sha256=sha(p),phase=c['phase'],issued_counts=count,candidates=[s for plan,s in pool],native_Q_N_s=native.tolist(),algebraic_Q_N_s=real.tolist(),contributions_N_s=contributions,native_rank=np.argsort(native,kind='stable').tolist(),algebraic_fixed_masked_plan_rank=np.argsort(real,kind='stable').tolist(),same_state_pairwise_float32_error_N_s=deltaerr))
  # Algebra probes vary only b, retain the exact same candidate/carry/count.
  # They do not claim these altered feature vectors are deployable states.
  rng=np.random.default_rng(2026100900+len(rows));variants=[x.copy()]
  for magnitude in (0.001,0.01,0.1):
   y=x.copy();shift=rng.normal(0,magnitude,58).astype(np.float32);y[:,:58]=x[:,:58]+shift;variants.append(y)
  differences=[]
  for y in variants:
   q=net.values(y);differences.append((q-q[0]).tolist())
  probes.append(dict(snapshot=p.name,scope='Algebraic feature-only counterfactual; not a new deployable Human/state',unchanged_U_carry_counts=True,native_pairwise_differences_N_s=differences,analytic_difference_state_derivative=0.,maximum_numeric_difference_drift_N_s=float(np.max(np.abs(np.asarray(differences)-differences[0])))))
 out=dict(status='STATE_DEPENDENCE_LIMITED',weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),feature_dim=120,state_times_plan_interactions=False,state_plan_cross_derivative=0.,state_specific_candidate_preference_expressible=False,rows=rows,feature_only_probes=probes,max_same_state_pairwise_float32_error_N_s=max(r['same_state_pairwise_float32_error_N_s'] for r in rows),max_float32_state_bias_subtraction_drift_N_s=max(r['maximum_numeric_difference_drift_N_s'] for r in probes),coefficient_tables_by_phase=coef[58:88].reshape(2,5,3).tolist(),physics_attempts_added=0,Q_updates=0,interpretation='Changing causal state adds a common real-arithmetic bias; any tiny difference drift is finite-precision arithmetic, not learned state×plan interaction. Issued masks remove delivered plan slots; carry/candidate pool identity, phase and native feasibility/realization remain state-dependent. Existing control improvement does not prove preference personalization.')
 out['interpretation']='Changing causal state adds a common real-arithmetic bias; tiny difference drift is finite precision, not learned state×plan interaction. Original coordinator count masks remove attempted plan positions; actual failed-prefix counts are not physically committed-action counts. Carry, candidate pool identity, phase and native feasibility/realization remain state-dependent. Existing control improvement does not prove preference personalization.'
 save(STUDY/'reports/Q_CURRENT_COUNTERFACTUAL_AUDIT.json',out);print(json.dumps({k:out[k] for k in ('status','feature_dim','state_times_plan_interactions','max_same_state_pairwise_float32_error_N_s','max_float32_state_bias_subtraction_drift_N_s','physics_attempts_added','Q_updates')}))
if __name__=='__main__':main()
