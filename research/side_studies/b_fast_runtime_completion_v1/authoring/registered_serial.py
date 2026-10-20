"""Serial registered trials. Each retains the original durable dispatcher guards."""
from pathlib import Path
import json, subprocess, sys, time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
W=Path(__file__).resolve().parent
def main():
    lo,hi=map(int,sys.argv[1:3])
    registration=json.loads((S/'versions/S2_FOLLOWUP_TEST_REGISTRATION.json').read_text())
    paths=[Path(p) for p in registration['configs'] if lo<=int(Path(p).name[:3])<=hi]
    assert len(paths)==hi-lo+1
    for path in paths:
        cfg=json.loads(path.read_text());ident=cfg['id']
        ledger=json.loads((S/'TASK_LEDGER.json').read_text())
        assert ident not in ledger, 'NO_REPLAY_OF_STARTED_ID'
        proc=subprocess.run([sys.executable,str(W/'fast_dispatch.py'),str(path)])
        assert proc.returncode==0, 'DISPATCH_FAILED_STOP_SERIES'
        result=json.loads((S/'output'/(ident+'_RESULT.json')).read_text())
        review=subprocess.run([sys.executable,str(W/'host_review.py'),ident],stdout=subprocess.DEVNULL)
        assert review.returncode==0, 'REVIEW_FAILED_STOP_SERIES'
        error=str(result.get('error',''))
        summary_path=S/'source/results'/ident/'summary.json'
        summary=json.loads(summary_path.read_text()) if summary_path.exists() else {}
        error+=' '+str(summary.get('abort_reason',''))
        print('REGISTERED_FINISH',ident,result['status'],error,flush=True)
        if 'BRAKE_INFEASIBLE' in error:raise RuntimeError('BRAKE_INFEASIBLE_REQUIRES_ROOT_CAUSE_BEFORE_NEW_RUN')
        if result['status']!='COMPLETE':
            assert cfg.get('fault_injection',{}).get('kind') in ('expired_result','explicit_native_rejection'), 'UNEXPECTED_FAILURE_STOP_SERIES'
            print('PRESERVED_EXPECTED_FAULT_FAILURE; next distinct registered case',flush=True)
if __name__=='__main__':main()
