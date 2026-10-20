"""Frozen causal-state, no-physics certificate/order equivalence sweep."""
from task_bootstrap import *
import pickle,types,numpy as np
def main():
 import study_common as sc,native_core as nc,shared_nominal,batched_mechanics
 from traction_mpc_stage5.architecture_recovery_v2 import phase3_human_waypoint as ph
 from native_inference import Networks
 original=ph.AdaptiveMechanicsScreenV22.evaluate;shared_nominal.install();batched_mechanics.install(dict(public_version='C2_THREAD',execution_mode='OFFLINE_SAVED_CAUSAL_STATE'))
 batch=ph.AdaptiveMechanicsScreenV22.evaluate;net=Networks(STUDY/'weights/frozen_Q_v1');files=sorted((STUDY/'output/STATE_SNAPSHOTS').rglob('*.pkl'));rows=[];errors=[]
 assert files,'NO_SAVED_NATIVE_STATES'
 for p in files:
  row=pickle.loads(p.read_bytes());clone,args=pickle.loads(row['payload']);b=dict(adaptive_planner=clone,arguments=args,request=types.SimpleNamespace(request_id=row['request_id'],sensor_capture_ns=row['sensor_capture_ns']));c=row['context'];count=row['count'];carry=row['carry'];rng=np.random.default_rng();rng.bit_generator.state=row['rng_state'];pool=nc.candidates(c,count,carry,int(rng.integers(1,2**31)),6);feature=np.asarray([nc.feature(c,plan,count,carry) for plan,source in pool]);results={};timings={}
  for version,method,cache in [('T0',original,False),('C2_E1',batch,True)]:
   ph.AdaptiveMechanicsScreenV22.evaluate=method;t=time.monotonic();records=[]
   ctx=shared_nominal.boundary(b) if cache else __import__('contextlib').nullcontext()
   with ctx:
    context_clone,context_args=pickle.loads(nc.snapshot_task_call(clone,args));context_clone.planner.residual_spec={};context_clone.decide(**context_args)
    for plan,source in pool:
     try:ev=nc.native_local(b,c,plan,count)
     except (ValueError,RuntimeError) as e:ev=dict(feasible=False,proposal_accepted=False,reason=str(e))
     records.append(ev)
   timings[version]=(time.monotonic()-t)*1000;results[version]=records
  a=results['T0'];z=results['C2_E1'];valid=[j for j,r in enumerate(a) if r['feasible'] and r['proposal_accepted']];values=net.values(np.asarray([feature[j] for j in valid])) if valid else [];baseline=valid[int(np.argmin(values))] if valid else 0;all_q=net.values(feature);order=sorted(range(len(pool)),key=lambda j:(float(all_q[j]),j));first=next((j for j in order if a[j]['feasible'] and a[j]['proposal_accepted']),0);accept=all((x['feasible'],x['proposal_accepted'],x.get('reason'))==(y['feasible'],y['proposal_accepted'],y.get('reason')) for x,y in zip(a,z));target=all(np.allclose(x.get('target',[]),y.get('target',[]),atol=1e-10,rtol=0) for x,y in zip(a,z));gap=min([abs(float(all_q[j]-all_q[baseline])) for j in valid if j!=baseline] or [float('inf')]);good=accept and target and baseline==first
  out=dict(snapshot=str(p),snapshot_sha256=sha(p),owner_request=row['request_id'],count=count,phase=c['phase'],candidate_count=len(pool),all_acceptance_exact=accept,all_targets_within_existing_tolerance=target,all_validate_subsetQ_choice=baseline,Q_first_complete_certificate_choice=first,Q_ranking_match=baseline==first,minimum_valid_Q_gap_N_s=None if not np.isfinite(gap) else gap,timing_ms=timings,status='PASS' if good else 'FAIL');rows.append(out)
  if not good:errors.append(out)
  print(json.dumps(dict(snapshot=p.parent.name+'/'+p.name,status=out['status'],timing_ms=timings)),flush=True)
 ph.AdaptiveMechanicsScreenV22.evaluate=original
 out=dict(status='PASS' if not errors else 'FAIL',rows=rows,physics_attempts_added=0,causal_states_from_native_boundaries=True,same_frozen_Q=True,all_candidates_certified_in_both_variants=True,explanation='These are saved deployable-model computations, not full repetition force predictions or new physical executions. Prefix-owned captured boundaries are counterfactual candidate checks, not claims that Q selected those prefix actions.',batch_calls=len(batched_mechanics.EVENTS));p=STUDY/'reports/OFFLINE_CAUSAL_CERTIFICATE_EQUIVALENCE.json'
 if p.exists():shutil.copy2(p,STUDY/'reports'/('OFFLINE_CAUSAL_CERTIFICATE_EQUIVALENCE_HISTORY_'+sha(p)+'.json'))
 save(p,out)
 print(json.dumps(dict(status=out['status'],states=len(rows),physics_attempts_added=0)))
if __name__=='__main__':main()
