"""Logging-only snapshot patch; original repository is never edited."""
from freeze import *
def main():
 src=STUDY/'source';root=STUDY/'source_history/model_call_accounting_v1';root.mkdir(parents=True,exist_ok=True)
 paths=[src/'stages/stage4_adaptive_control/src/traction_mpc_stage4/estimator_v2.py',src/'stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/online_planning.py']
 changes=[]
 for p in paths:
  text=p.read_text()
  if 'RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS' in text or 'research_model_invocations' in text:continue
  shutil.copy2(p,root/p.name);before=sha(p)
  if p.name=='estimator_v2.py':
   needle='        regressor = dynamic_regressor_row(q_rad, dq_rad_s, ddq_rad_s2)'
   assert text.count(needle)==1
   text=text.replace(needle,'        global RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS\n        RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS += 1\n'+needle)
   text+='\n# Research accounting only: API calls, not physical simulator steps.\nRESEARCH_MODEL_INVERSE_DYNAMICS_CALLS = 0\n'
  else:
   text=text.replace('    started = monotonic_ns()\n    try:\n        value = execute_task_snapshot(payload)','    started = monotonic_ns()\n    from traction_mpc_stage4 import estimator_v2 as model_accounting\n    model_count_start = model_accounting.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS\n    try:\n        value = execute_task_snapshot(payload)')
   text=text.replace('    result.update(worker_start_ns=started, compute_finish_ns=monotonic_ns())','    result.update(worker_start_ns=started, compute_finish_ns=monotonic_ns(), research_model_invocations=model_accounting.RESEARCH_MODEL_INVERSE_DYNAMICS_CALLS-model_count_start)')
   text=text.replace('"worker_exception", "terminal_reference_selection"):', '"worker_exception", "terminal_reference_selection", "research_model_invocations"):')
  p.write_text(text);changes.append(dict(path=str(p),before_sha256=before,after_sha256=sha(p),semantics='integer counter and returned logging field only; arithmetic, candidates, timing, outcomes unchanged'))
 manifest=json.loads((STUDY/'SOURCE.json').read_text())
 for p in paths:manifest['frozen_files'][str(p)]=sha(p)
 save(STUDY/'SOURCE.json',manifest);save(root/'PATCH_MANIFEST.json',dict(changes=changes,scientific_changes=[],original_project_edited=False))
 print(json.dumps(dict(logging_patches=len(changes))))
if __name__=='__main__':main()
