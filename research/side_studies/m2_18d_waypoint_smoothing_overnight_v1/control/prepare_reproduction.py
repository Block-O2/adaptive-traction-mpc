"""Prepare a fresh reproduction without executing any physics.

Use the finalized canonical package as source; never reset old attempts.
"""
from pathlib import Path
import argparse,json,shutil,time,hashlib
src=Path(__file__).resolve().parents[1];args=argparse.ArgumentParser();args.add_argument('--destination',required=True);opts=args.parse_args();dst=Path(opts.destination).resolve()
assert dst.parent==src.parent and dst!=src and not dst.exists(),'Use a new sibling package directory'
dst.mkdir()
for name in ['source','code','deps','weights','control','tests']:
 shutil.copytree(src/name,dst/name,ignore=shutil.ignore_patterns('results','__pycache__','*.pyc'))
for name in ['output','motion_series','series','reports','audit','tmp','logs','figures']:(dst/name).mkdir(exist_ok=True)
for name in ['CANDIDATE_PLAN.json','EXECUTABLE_PLAN.json','MOTION_ACCEPTANCE_PROTOCOL.json','CERTIFICATION_TEST_RESULTS.json','DENSITY_MATH_TESTS.json','TARGETED_MATH_TESTS.json']:
 shutil.copy2(src/name,dst/name)
shutil.copy2(src/'output/SHARED_COORDINATION_ACTION_CONTRACT.json',dst/'output/SHARED_COORDINATION_ACTION_CONTRACT.json')
(dst/'key_traces').symlink_to((src/'key_traces').resolve(),target_is_directory=True)
for name in ['source','code','deps','control','tests']:
 for f in (dst/name).rglob('*'):
  if f.is_file() and f.suffix in ['.py','.json','.xml','.yaml','.yml','.toml']:
   try:s=f.read_text()
   except UnicodeError:continue
   if str(src) in s:f.write_text(s.replace(str(src),str(dst)))
plan=json.loads((src/'RUN_PLAN.json').read_text());now=time.time();plan.update(physics_budget=12,dispatch_cutoff_unix=now+7200,physics_hard_stop_unix=now+7500);plan.pop('engineering_amendment',None);plan['reproduction_of']=str(src);(dst/'RUN_PLAN.json').write_text(json.dumps(plan,indent=2))
manifest={str(f.relative_to(dst)):hashlib.sha256(f.read_bytes()).hexdigest() for name in ['source','code','deps','weights','control','tests'] for f in (dst/name).rglob('*') if f.is_file() and '__pycache__' not in f.parts};(dst/'EXECUTION_CODE_MANIFEST.json').write_text(json.dumps(dict(files=manifest,executable_plan_sha256=hashlib.sha256((dst/'EXECUTABLE_PLAN.json').read_bytes()).hexdigest(),run_plan_sha256=hashlib.sha256((dst/'RUN_PLAN.json').read_bytes()).hexdigest(),source_package=str(src)),indent=2))
print('PREPARED_ONLY_NO_PHYSICS',dst)
print('Run only after deliberately requesting a fresh reproduction:')
print('/home/hank/envs/adaptive-online-rl-v1/bin/python -B '+str(dst/'control/targeted_campaign_repair1.py'))
