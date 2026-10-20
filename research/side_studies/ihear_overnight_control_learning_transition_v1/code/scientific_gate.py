from pathlib import Path
import sys,json,time
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_control_learning_transition_v1');O=S.parent/'b_multirate_realtime_v1';sys.path.insert(0,str(S/'code'))
from full_native_equivalence import full_compare
from task_bootstrap import save,sha
def main():
 new=sys.argv[1];kind=sys.argv[2];old='020_R3_nominal' if kind=='nominal' else '021_R3_deviation';alias='REFERENCE_'+old
 for target,path in [(O/'source/results'/old,S/'source/results'/alias),(O/'output'/(old+'_RESULT.json'),S/'output'/(alias+'_RESULT.json'))]:
  assert target.exists(),target
  if not path.exists():path.symlink_to(target,target_is_directory=target.is_dir())
 row=full_compare(alias,new);out=dict(version=new,status=row['status'],rows=[row],source_authority=str(O/'versions/R3_SCIENTIFIC_GATE.json'),authority_sha256=sha(O/'versions/R3_SCIENTIFIC_GATE.json'),reference_copy_policy='Read-only symlink to immutable historical baseline; no raw copying',atol=1e-10,registered_before_physics=True,unix=time.time())
 save(S/'versions'/(new+'_SCI_GATE.json'),out);print(json.dumps(dict(id=new,status=out['status'],issues=row['issues'],native_max_errors=row['full_native_step_max_errors'],trace_max_errors={k:v for k,v in row['trace_max_abs_errors'].items() if v!=0})))
if __name__=='__main__':main()
