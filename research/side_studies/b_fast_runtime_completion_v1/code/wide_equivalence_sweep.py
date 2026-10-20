"""Expanded B4 offline certification/order proof; no new physics or E search.

Only the existing frozen six-candidate generator on saved causal states.
No plans are optimized against actual force; repeated identical pools skip.
"""
from task_bootstrap import *
import pickle,types,numpy as np
def main():
 import study_common as sc,native_core as nc,shared_nominal,batched_mechanics,runner
 from traction_mpc_stage5.architecture_recovery_v2 import phase3_human_waypoint as ph
 from native_inference import Networks
 original=ph.AdaptiveMechanicsScreenV22.evaluate;shared_nominal.install();batched_mechanics.install(dict(public_version='C2_THREAD',execution_mode='OFFLINE_SAVED_CAUSAL_STATE'));batch=ph.AdaptiveMechanicsScreenV22.evaluate;net=Networks(STUDY/'weights/frozen_Q_v1')
 files=sorted((STUDY/'output/STATE_SNAPSHOTS/061_E3T_science_M2').glob('*.pkl'))+sorted((STUDY/'output/STATE_SNAPSHOTS/062_E3T_science_deviation').glob('*.pkl'));assert len(files)==22;rows=[];seen={str(p):set() for p in files};start=time.time();nextresource=start;nextsave=start;duplicates=0;validation_calls=0;errors=[]
 contract=dict(id='O10_WIDE_EQUIVALENCE',seed_start=2026100800,seeds=512,saved_causal_states=22,physics_attempts=0,model_full_repetition_predictions=0,same_frozen_Q=True,scope='B4 counterfactual certificate/order equivalence only; original generator, unchanged exposed nominal/deviation states; no candidate search against physical outcomes',deduplicate='Full same-state candidate identity byte sequence; identical pools never retested',wall_cap_s=3600,algorithm_sources={str(STUDY/'code'/f):sha(STUDY/'code'/f) for f in ('wide_equivalence_sweep.py','native_core.py','shared_nominal.py','batched_mechanics.py','native_inference.py')})
 save(STUDY/'versions/O10_WIDE_EQUIVALENCE_CONTRACT.json',contract)
 def checkpoint(final=False):
  out=dict(status='FAIL' if errors else ('PASS' if final else 'RUNNING'),rows=rows,comparisons=len(rows),native_validation_calls=validation_calls,duplicate_pools_skipped=duplicates,elapsed_s=time.time()-start,physics_attempts_added=0,errors=errors,Q_weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),contract=contract,completeness='All completed unique pools include six-candidate full certificates in both scalar original and C2/shared-context variants. A wall-bounded partial seed sweep cannot imply full continuous-space coverage.')
  save(STUDY/'reports/WIDE_CAUSAL_EQUIVALENCE.json',out)
 for seedindex in range(contract['seeds']):
  for p in files:
   if time.time()-start>contract['wall_cap_s'] or time.time()>=START+8.25*3600:checkpoint(True);return
   if time.time()>=nextresource:runner.sample(filename='OFFLINE_RESOURCE_LOG.jsonl');nextresource=time.time()+45
   row=pickle.loads(p.read_bytes());c=row['context'];count=row['count'];carry=row['carry'];seed=contract['seed_start']+seedindex;pool=nc.candidates(c,count,carry,seed,6);poolkey=hashlib.sha256(pickle.dumps(pool,protocol=5)).hexdigest()
   if poolkey in seen[str(p)]:duplicates+=1;continue
   seen[str(p)].add(poolkey);features=np.asarray([nc.feature(c,plan,count,carry) for plan,source in pool]);results={};timings={}
   for version,method,cache in [('T0',original,False),('C2_E1',batch,True)]:
    clone,args=pickle.loads(row['payload']);b=dict(adaptive_planner=clone,arguments=args,request=types.SimpleNamespace(request_id=row['request_id'],sensor_capture_ns=row['sensor_capture_ns']));ph.AdaptiveMechanicsScreenV22.evaluate=method;t=time.monotonic();records=[];scope=shared_nominal.boundary(b) if cache else __import__('contextlib').nullcontext()
    with scope:
     context_clone,context_args=pickle.loads(nc.snapshot_task_call(clone,args));context_clone.planner.residual_spec={};context_clone.decide(**context_args)
     for plan,source in pool:
      try:ev=nc.native_local(b,c,plan,count)
      except (ValueError,RuntimeError) as e:ev=dict(feasible=False,proposal_accepted=False,reason=str(e))
      records.append(ev);validation_calls+=1
    timings[version]=(time.monotonic()-t)*1000;results[version]=records
   a,z=results['T0'],results['C2_E1'];valid=[j for j,r in enumerate(a) if r['feasible'] and r['proposal_accepted']];subset=net.values(features[valid]) if valid else [];baseline=valid[int(np.argmin(subset))] if valid else 0;allq=net.values(features);order=sorted(range(len(pool)),key=lambda j:(float(allq[j]),j));first=next((j for j in order if j in valid),0)
   norm=net.scale(features);eps=np.finfo(np.float32).eps;gamma=features.shape[1]*eps/(1-features.shape[1]*eps);bounds=2*gamma*(np.abs(norm)@np.abs(net.w['linear_W']))*abs(float(net.w['y_scale']))+4*eps*np.abs(allq);pos=order.index(first) if valid else 0;fallback=bool(valid and any(float(allq[k]-allq[first])<=float(bounds[k]+bounds[first]) for k in order[pos+1:]));chosen=baseline if fallback else first
   accept=all((x['feasible'],x['proposal_accepted'],x.get('reason'))==(y['feasible'],y['proposal_accepted'],y.get('reason')) for x,y in zip(a,z));target=all(np.allclose(x.get('target',[]),y.get('target',[]),atol=1e-10,rtol=0) for x,y in zip(a,z));good=accept and target and baseline==chosen
   r=dict(snapshot=p.parent.name+'/'+p.name,state_sha256=sha(p),seed=seed,pool_sha256=poolkey,candidate_count=len(pool),native_acceptance_exact=accept,target_within_frozen_1e_10=target,original_selected=baseline,Q_first_selected=chosen,raw_all_batch_rank_selected=first,roundoff_fallback=fallback,feasible_count=len(valid),timing_ms=timings,status='PASS' if good else 'FAIL');rows.append(r)
   if not good:errors.append(r);checkpoint(True);raise RuntimeError('WIDE_EQUIVALENCE_MISMATCH')
   batched_mechanics.EVENTS.clear();shared_nominal.EVENTS.clear()
   if time.time()>=nextsave:checkpoint();print(json.dumps(dict(comparisons=len(rows),seed_index=seedindex,elapsed_s=time.time()-start,errors=len(errors),physics_attempts=0)),flush=True);nextsave=time.time()+1200
 checkpoint(True);print(json.dumps(dict(status='PASS',comparisons=len(rows),native_validation_calls=validation_calls,duplicates_skipped=duplicates,elapsed_s=time.time()-start,physics_attempts=0)))
if __name__=='__main__':main()
