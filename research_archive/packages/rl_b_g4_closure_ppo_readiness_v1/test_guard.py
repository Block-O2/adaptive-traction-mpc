"""TEST_ONLY resource fault injection; no high-load child is launched."""
from pathlib import Path
import tempfile,json
import resource_guard as r
tests=[];original=r.sample
def test(name,row,expect):
 with tempfile.TemporaryDirectory(dir=r.R) as folder:
  g=r.Guard(Path(folder));r.sample=lambda:row
  try:g.poll();passed=not expect
  except r.ResourceStop:passed=expect
  tests.append({'test':name,'pass':passed});g.close()
base={'unix':0,'available_bytes':6*r.GiB,'total_bytes':16*r.GiB,'swap_used_bytes':0,'disk_free_bytes':10*r.GiB}
try:
 test('TEST_ONLY_good_sample',base,False)
 test('TEST_ONLY_memory_below_3GiB',{**base,'available_bytes':3*r.GiB-1},True)
 test('TEST_ONLY_disk_reserve',{**base,'disk_free_bytes':r.GiB},True)
 with tempfile.TemporaryDirectory(dir=r.R) as folder:
  g=r.Guard(Path(folder));r.sample=lambda:(_ for _ in ()).throw(OSError('TEST_ONLY_MONITOR_FAILURE'))
  try:g.poll();passed=False
  except r.ResourceStop:passed=True
  tests.append({'test':'TEST_ONLY_monitor_failure_stops','pass':passed})
 with tempfile.TemporaryDirectory(dir=r.R) as folder:
  g=r.Guard(Path(folder));g.initial_swap=0;r.sample=lambda:{**base,'swap_used_bytes':256*1024**2}
  try:
   for i in range(5):g.poll()
   passed=False
  except r.ResourceStop:passed=True
  tests.append({'test':'TEST_ONLY_sustained_swap_growth_stops','pass':passed})
finally:r.sample=original
out={'category':'TEST_ONLY_RESOURCE_PROTOCOL','pass':all(x['pass'] for x in tests),'tests':tests};(r.R/'GUARD_UNIT_RESULTS.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
if not out['pass']:raise SystemExit(1)
