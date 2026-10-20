from pathlib import Path
import json,time,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
def main():
 p=S/'code/runner.py';text=p.read_text()
 anchor=" row=dict(unix=time.time(),owner=owner,mem_available="
 if 'cpu_ticks_system=' not in text:
  assert anchor in text
  text=text.replace(anchor," row=dict(cpu_load=os.getloadavg(),cpu_ticks_system=[int(v) for v in Path('/proc/stat').read_text().splitlines()[0].split()[1:]],clock_ticks=os.sysconf('SC_CLK_TCK'),unix=time.time(),owner=owner,mem_available=")
  old="cmd=(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace')))"
  new="cmd=(p/'cmdline').read_bytes().replace(b'\\0',b' ').decode(errors='replace'),cpu_ticks=[int(v) for v in (p/'stat').read_text().rsplit(') ',1)[1].split()[11:13]]))"
  assert old in text;text=text.replace(old,new);p.write_text(text)
 plan=json.loads((S/'RUN_PLAN.json').read_text());ledger=json.loads((S/'TASK_LEDGER.json').read_text())
 with (S/'PROGRESS.md').open('a') as f:
  f.write(f'\nCheckpoint {time.strftime("%Y-%m-%d %H:%M:%S",time.gmtime())} UTC; elapsed {(time.time()-plan["t0_unix"])/3600:.3f}h.\n')
  f.write('N4 exact soft limits reduce plant median to 46.44us. N4/V2 expanded exact vector path + C2 poll deadline passes all frozen service/miss/rolling/backlog checks in host018 (p50 5.009ms, p95 5.623ms, p99 6.742ms); 118405 actual steps have zero causal violations. Full physical task PASS, original R2 remains FAIL (HOLD1.06s, OUT9.3s following fallback). Native004/N1 is negative; R1 full-model key closed; R2 small numerical cache is correct but overhead outweighs benefit. N4/V2 nominal and legal-deviation SCI bit-exact PASS. W1 per-request exact proof reuse decision+proof local PASS and full SCI020 bit-exact PASS. D1 direct immutable atomic TASK IPC local PASS, full SCI021 underway; original planner,100ms/current admission and one live plant unchanged. Next: D1 host, then further phase/receipt ownership optimization if R2 remains. No learning enabled.\n')
  f.write(f'Physical attempts including cost runs/startup failures: {len(ledger)}/{plan["physics_budget"]}; no repeated completed IDs. Resource baseline healthy; CPU accounting added for subsequent 45s samples, early sampling gap disclosed.\n')
 manifest={str(p.relative_to(S)):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('code','native','build') for p in (S/root).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 target=S/'versions'/('CHECKPOINT_CODE_'+str(int(time.time()))+'.json');target.write_text(json.dumps(manifest,indent=2)+'\n');print('CHECKPOINT_SAVED',len(ledger))
if __name__=='__main__':main()
