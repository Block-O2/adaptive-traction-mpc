from pathlib import Path
import json,time,shutil,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1');base=json.loads((S/'queue/048_N13_C2b_host.json').read_text());configs=[]
for n in range(60,64):
 cfg=base|dict(id=f'{n:03d}_N13_S1_REUSE4_{n-59}',seed=2026100700+n,fast_version=base['fast_version']+'_S1',dependencies=['059_N13_S1_science_nominal'],required_gates=['versions/059_N13_S1_science_nominal_SCI_GATE.json','output/STREAM_REUSE_LOCAL_REGRESSION.json'],series='independent_runtime_diagnostic')
 configs.append(cfg)
out=dict(id='N13_S1_REUSE4',same_interpreter=True,configs=configs,registered_unix=time.time(),previous_cohort='N13_C2b_REUSE4',previous_failure='058 SERIALIZER_SOURCE_CHANGED: preserved, unstarted059/060 previous-group labels remain unattempted',purpose='Complete4 same-interpreter full tasks after S1 serializer owner/closure repair; unchanged mathematics and qualification criteria.',physical_session_continuous=False)
p=S/'queue/N13_S1_REUSE4.json';assert not p.exists();p.write_text(json.dumps(out,indent=2)+'\n')
dest=S/'versions/N13_S1_COHORT_CODE';assert not dest.exists();dest.mkdir()
for root in ('code','native','build'):shutil.copytree(S/root,dest/root,ignore=shutil.ignore_patterns('__pycache__'))
(dest/'MANIFEST.json').write_text(json.dumps({str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()},indent=2)+'\n')
with (S/'PROGRESS.md').open('a') as f:f.write('\nCOLD4 all full physical/current/causal PASS, allHOLD R2FAIL; fourth rolling1s max6.068ms >frozen6msFAIL. OriginalREUSE4 first full task then058 serializer repeat-install failed0physics; no unchanged retries, oldcode/result retained. S1 installs original streaming serializer once and restores base function instead of prior-run closure;5localcasesPASS, fullSCI059 pending. W3 complete-model/torque/q allocation reuse3012 localcases and all6 saveddecision/proof/randomized pairs bit-exact with same14280 modelAPIcalls; HOLD slower.096/.211ms andmovingworkers slower7–8ms: closedlocal-only, notenabled onplant. New S1 reused-interpreter4run queue frozen, originalfailures unchanged.\n')
print('S1_REUSE4_REGISTERED')
