from task_bootstrap import *
def freeze(version):
 files=[]
 actor={'worker.py','study_common.py','native_method.py','native_core.py','native_inference.py','interfaces.py','optimized_method.py','optimized_e3.py','shared_nominal.py','certified_snapshot.py','certified_snapshot_v2.py','certified_apply.py','capture_states.py','public_worker.py','batched_mechanics.py','call_audit.py','profiling_instrumentation.py','consecutive_worker.py','accounting.py','task_bootstrap.py','mode_metadata.py','async_native_main.py','async_native_worker.py','q_first_method.py','lean_instrumentation.py','continuous_worker.py','deferred_evaluation.py'}
 for root in [STUDY/'source',STUDY/'deps',STUDY/'code',STUDY/'weights/frozen_Q_v1']:
  for p in sorted(root.rglob('*')):
   if not p.is_file() or p.suffix=='.pyc' or '__pycache__' in p.parts:continue
   if root.name=='code' and p.name not in actor:continue
   if root.name=='source' and p.relative_to(root).parts[0]=='results':continue
   files.append(p)
 sources={str(p):sha(p) for p in files};out=dict(version=version,created_unix=time.time(),scientific_version='frozen-B-native-Q-v1',weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),files=sources,source_and_options_and_assets_frozen=True)
 p=STUDY/'versions'/(version+'_FROZEN_MANIFEST.json')
 if p.exists():assert json.loads(p.read_text())['files']==sources,'DO_NOT_MUTATE_FROZEN_VERSION'
 else:save(p,out)
 return out
def main():
 v=freeze(sys.argv[1]);print(json.dumps(dict(version=v['version'],files=len(v['files']),weights_sha256=v['weights_sha256'])))
if __name__=='__main__':main()
