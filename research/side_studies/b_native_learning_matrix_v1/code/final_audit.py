from task_bootstrap import *
import os,numpy as np

def main():
 status=json.loads((STUDY/'FINAL_STATUS.json').read_text())
 assert status['status']=='COMPLETE_STOPPED'
 frozen=json.loads((STUDY/'SOURCE.json').read_text())['frozen_files']
 assert all(sha(Path(p))==h for p,h in frozen.items()),'FROZEN_BASE_CHANGED'
 active=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  except OSError:continue
  if str(STUDY) in cmd and any('/'+role+'.py' in cmd for role in ('runner','worker','controller','train_native')):active.append(dict(pid=int(p.name),cmd=cmd))
 assert not active,'STUDY_PROCESS_STILL_ACTIVE'
 raw=list((STUDY/'source/results').glob('*/runtime_artifacts.json'));assert not raw,'UNARCHIVED_RUNTIME_DUPLICATE'
 with np.load(STUDY/'source/results/002_original_B_retry1/trace.npz') as a:
  for name in ('040_v1_0_nominal_a_M0','040_v1_1_nominal_b_M0','080_v1_repeat_0_nominal_c_M0','080_v1_repeat_1_nominal_d_M0'):
   with np.load(STUDY/'source/results'/name/'trace.npz') as b:
    assert set(a.files)==set(b.files)
    for k in a.files:assert np.array_equal(a[k],b[k],equal_nan=True) if a[k].dtype.kind in 'fiu' else np.array_equal(a[k],b[k]),name+':'+k
 report=(STUDY/'FINAL_REPORT.md').read_text();assert 'COMPLETE_STOPPED' in report and 'NOT_RUN' in report
 out=dict(status='PASS',unix=time.time(),frozen_base_files=len(frozen),frozen_base_unchanged=True,study_processes_active=active,unarchived_runtime_duplicates=0,all_four_nominal_M0_traces_exact=True,final_report_sha256=sha(STUDY/'FINAL_REPORT.md'),manifest_sha256=sha(STUDY/'FINAL_MANIFEST.json'),no_pending_physics=True)
 save(STUDY/'FINAL_AUDIT.json',out)
 print(json.dumps(out))
if __name__=='__main__':main()
