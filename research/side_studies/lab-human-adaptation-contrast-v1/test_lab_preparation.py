"""Offline regression checks for gating and immutable causal model snapshots."""
from pathlib import Path
import os,sys,json,hashlib,importlib.util
for n in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[n]='1'
os.environ['CUDA_VISIBLE_DEVICES']='';sys.dont_write_bytecode=True
W=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/lab-human-adaptation-contrast-v1');sys.path.insert(0,str(W))
from lab_resource_guard import gate_reasons,verify_release
spec=importlib.util.spec_from_file_location('lab_harness_checked',W/'human_qualification.py');harness=importlib.util.module_from_spec(spec);spec.loader.exec_module(harness)
import numpy as np
results=[]
good={'WSL_available_GiB':7.,'Windows_available_GiB':9.,'explicit_benchmark_phase':False,'swap_used_KiB':0}
assert gate_reasons(good,3.,True,True)==[];results.append('generous resources qualify if evidence/stage verified')
assert 'WINDOWS_PROJECTED_RESERVE_LT_4GiB' in gate_reasons({**good,'Windows_available_GiB':6.99},3.,True,True);results.append('Windows projected reserve boundary refuses')
assert 'WSL_RESERVE_BEYOND_SIDE_PEAK_LT_2GiB' in gate_reasons({**good,'WSL_available_GiB':4.99},3.,True,True);results.append('WSL peak+2 boundary refuses')
assert 'SAC_FORMAL_BENCHMARK_EXCLUSION_NOT_CONFIRMED' in gate_reasons({**good,'explicit_benchmark_phase':True},3.,True,True);results.append('SAC benchmark blocks regardless of RAM')
assert 'NO_VERIFIED_AGGREGATE_PARENT_PLANNER_PEAK' in gate_reasons(good,3.,False,True);results.append('missing aggregate peak evidence refuses')
assert 'SAC_FORMAL_BENCHMARK_EXCLUSION_NOT_CONFIRMED' in gate_reasons(good,3.,True,False);results.append('ambiguous SAC phase refuses')
assert not (W/'RESOURCE_RELEASE.json').exists()
try:verify_release('unused')
except RuntimeError as e:assert 'READY_WAITING_FOR_RESOURCES' in str(e);results.append('absent release refuses before physics launch')
else:raise AssertionError('release absence did not block')
m=harness.rt.nominal_control_model();frozen=harness.copy_causal_model(m);q=np.radians([20.,30.]);dq=np.array([.1,-.2]);ddq=np.array([.3,.4]);before=frozen.inverse_dynamics(q,dq,ddq).copy()
m.beta[0]+=100;m.residual_weights_nm[0,0]+=3
assert np.array_equal(before,frozen.inverse_dynamics(q,dq,ddq)) and not np.shares_memory(m.beta,frozen.beta) and not np.shares_memory(m.residual_weights_nm,frozen.residual_weights_nm);results.append('commissioning prediction checkpoint survives later beta/residual mutation')
harness.validate_only()
c=json.loads((W/'CONTRACT.json').read_text());base=c['conditions'][0]['case']['physical']
expected={'C1':{'body_mass_kg'},'C2':{'body_mass_kg'},'C3':{'passive_stiffness_nm_rad'},'C4':{'passive_stiffness_nm_rad'},'C5':{'cuff_fraction_of_shank'},'C6':{'cuff_fraction_of_shank'}}
for e in c['conditions'][1:]:
 different={k for k,v in e['case']['physical'].items() if v!=base[k]};assert different==expected[e['id']],(e['id'],different)
 assert e['case']['task']==c['conditions'][0]['case']['task']
results.append('all six nonnominal fixtures differ along exactly one requested physical factor')
assert not (W/'runs').exists() and not (W/'OWNER.lock').exists()
(W/'PREPARATION_REGRESSION.json').write_text(json.dumps({'status':'PASS_STATIC_ONLY','checks':results,'dynamic_runs':0,'regression_reason':'Wrapper geometry field repaired; effective cuff centers matched original fixture in static audit. Guard boundaries and immutable TASK prediction model tested. No production edits.','dynamic_runner_not_tested':True},indent=2)+'\n')
print(json.dumps({'status':'PASS_STATIC_ONLY','checks':len(results),'dynamics':0}))
