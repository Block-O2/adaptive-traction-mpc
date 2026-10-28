"""Explicit on-target qualification; TEST_ONLY results never replace physical tasks."""
from common import ROOT,put
import argparse,json,os,subprocess,sys
def run(argv):
 p=subprocess.run([sys.executable,*argv],cwd=ROOT)
 if p.returncode:raise RuntimeError('SUBCOMMAND_FAILED:'+str(argv))
def main():
 p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');p.add_argument('--prefix',default='cloud_qualification_01');a=p.parse_args()
 if not a.enable:raise RuntimeError('DISABLED_REQUIRE_EXPLICIT_ENABLE')
 from checkpoints import contract
 from preflight import runtime
 base='runs/'+a.prefix
 if (ROOT/base).exists():raise RuntimeError('NEW_ATTEMPT_PREFIX_REQUIRED')
 (ROOT/base).mkdir(parents=True)
 put(ROOT/'READINESS.json',{'G4_TERMINATION_REWARD_PASS':'NOT_RUN','RL_EXECUTION_CONTRACT_PASS':'NOT_RUN','RL_TASK_REACHABILITY_PASS':'NOT_RUN','reason':'On-target qualification in progress; prior gate invalidated'})
 run(['test_g4.py']);run(['test_execution_contract.py']);run(['test_guard.py']);run(['preflight.py'])
 tests={n:json.loads((ROOT/n).read_text()) for n in ('G4_UNIT_RESULTS.json','EXECUTION_CONTRACT_TESTS.json','GUARD_UNIT_RESULTS.json')}
 if not all(x.get('pass') for x in tests.values()):raise RuntimeError('UNIT_GATE_FAILED')
 for policy in ('hold','maximal','random'):
  out=f'{base}/{policy}'
  run(['resource_guard.py','--out',out,'--seconds','240','--',sys.executable,'run_rollout.py','--enable','--policy',policy,'--out',out+'/physics'])
 from verify_physics import audit
 evidence={policy:audit(ROOT/f'{base}/{policy}/physics',policy) for policy in ('hold','maximal','random')}
 put(ROOT/base/'QUALIFICATION_RESULT.json',{'tests':tests,'physics':evidence})
 execution_success=all(x['pass'] for x in evidence.values())
 # The inherited three tasks do not cover every required real G4 failure path.
 # A missing or incomplete cloud physical matrix must never promote training.
 matrix_path=ROOT/'G4_PHYSICAL_VALIDATION.json'
 matrix=json.loads(matrix_path.read_text()) if matrix_path.exists() else {}
 g4_success=(matrix.get('status')=='PASS' and matrix.get('all_key_real_failure_paths_closed') is True
             and matrix.get('contract_sha256')==contract() and matrix.get('runtime')==runtime())
 success=execution_success and g4_success
 gate={'G4_TERMINATION_REWARD_PASS':'PASS' if g4_success else 'NOT_RUN',
       'RL_EXECUTION_CONTRACT_PASS':'PASS' if execution_success else 'FAIL',
       'RL_TASK_REACHABILITY_PASS':'PASS' if execution_success else 'FAIL'}
 gate.update(contract_sha256=contract(),runtime=runtime(),evidence=base+'/QUALIFICATION_RESULT.json',scope='nominal scientific simulation only; no host realtime, patient or trained-policy qualification')
 put(ROOT/'READINESS.json',gate)
 if not success:raise RuntimeError('PHYSICS_GATE_FAILED')
if __name__=='__main__':main()
