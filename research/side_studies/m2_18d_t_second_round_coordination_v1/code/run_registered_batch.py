from pathlib import Path
import sys,subprocess,json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1');sys.dont_write_bytecode=True
def main():
 mode=sys.argv[1]
 if mode=='diagnostic':ids=['006_B_threadCPU_nominal','007_B_threadCPU_deviation']
 elif mode=='pairs':ids=[ident for p in json.loads((S/'reports/PAIR_REGISTRATION.json').read_text())['pairs'] for ident in p['ids']]
 else:raise ValueError(mode)
 for ident in ids:
  ledger=json.loads((S/'TASK_LEDGER.json').read_text());assert ident not in ledger,'No implicit repeats'
  print('BATCH_DISPATCH',ident,flush=True)
  subprocess.run([sys.executable,str(S/'code/fast_dispatch.py'),str(S/'queue'/(ident+'.json'))],check=True)
  subprocess.run([sys.executable,str(S/'code/review_attempt.py'),ident],check=True)
  axis=json.loads((S/'reports'/(ident+'_AXES.json')).read_text())
  if axis['PHYSICAL_TASK_VALID']!='PASS' or axis['HOST_EXECUTION_CAUSAL_VALID']!='PASS':
   (S/'reports/BATCH_STOP.json').write_text(json.dumps(dict(id=ident,mode=mode,unix=time.time(),reason='Inspect actual physical/native execution or causal failure before any new heavy dispatch',axes=axis),indent=2)+'\n');raise RuntimeError('NATIVE_OR_CAUSAL_FAILURE: '+ident)
 print('BATCH_COMPLETE',mode,flush=True)
if __name__=='__main__':main()
