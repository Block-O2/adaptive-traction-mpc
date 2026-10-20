"""Isolated frozen-binary counterexamples, no live plant or physics."""
from pathlib import Path
import sys,json,hashlib,dataclasses,numpy as np
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');branch=sys.argv[1]
assert branch in ('N4a_negative','N13a_negative_scalar_truth')
frozen=S/'versions'/branch;sys.path.insert(0,str(S/'code'));sys.path.insert(0,str(frozen))
import fast_native as native
assert Path(native.__file__).resolve().is_relative_to(frozen)
if branch=='N13a_negative_scalar_truth':
 rows=[]
 for x in (np.array([True]),np.array([False]),np.array([True,True]),np.array([True,False])):
  for any_value in (False,True):
   want=np.any(x) if any_value else np.all(x);got=native.small_bool_reduce(x,any_value)
   rows.append(dict(input=x.tolist(),any_value=any_value,expected_repr=repr(want),actual_repr=repr(got),expected_byte=want.tobytes().hex(),actual_byte=got.tobytes().hex(),expected_truth=bool(want),actual_truth=bool(got),actual_is_canonical_true=got is np.True_))
 assert any(r['expected_truth']!=r['actual_truth'] for r in rows)
 out=dict(status='NEGATIVE_COUNTEREXAMPLE_REPRODUCED',rows=rows,original_failed_test_evidence='OFFLINE_LEDGER original controller replay fail: valid held target rejected',negative_cause='Noncanonical NumPy Bool scalar byte/value and truth differ under installed NumPy2.2.6; fixed candidate returns original singleton.')
else:
 import study_common as sc
 from traction_mpc_stage3.human import soft_limit_torque,HUMAN
 from native_soft_limits import parameter_key
 rng=np.random.default_rng(20261007);bad=[];maxerr=0.
 for i in range(5000):
  h=dataclasses.replace(HUMAN,soft_limit_margin_rad=float(rng.uniform(.001,.2)),soft_limit_boundary_torque_nm=float(rng.uniform(1,100)),soft_limit_damping_nms_rad=float(rng.uniform(0,10)))
  q=rng.uniform(-4,4,2);dq=rng.uniform(-10,10,2);want=soft_limit_torque(q,dq,h);got=native.soft_limit_arrays(q,dq,np.asarray(parameter_key(h)))
  err=float(np.max(np.abs(want-got)));maxerr=max(maxerr,err)
  if want.tobytes()!=got.tobytes():bad.append(dict(index=i,parameters=list(parameter_key(h)),q=q.tolist(),dq=dq.tolist(),expected=want.tolist(),actual=got.tolist(),max_abs_error=err))
 assert bad
 out=dict(status='RECOVERED_NEGATIVE_COUNTEREXAMPLE',cases=5000,mismatches=len(bad),max_abs_error=maxerr,rows=bad[:5],original_gate_payload_retained=False,note='Original N4a gate JSON was overwritten by fixed N4 test before preservation. This is a new deterministic replay of the frozen original negative binary/source, explicitly NOT the original timestamped output.',negative_cause='Compiler constant-pow strength reduction differs from original Python libm pow; fixed backend uses volatile pow function pointer.')
out.update(branch=branch,no_physics=True,actual_binary=str(native.__file__),binary_sha256=hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),numpy_version=np.__version__)
(S/'reports'/(branch+'_RECOVERED_COUNTEREXAMPLE.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
