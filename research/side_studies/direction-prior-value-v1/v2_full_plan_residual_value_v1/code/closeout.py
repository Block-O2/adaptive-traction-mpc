from common import *
def main():
 code=NEW/'code';code.mkdir(exist_ok=True)
 for p in LOCAL.glob('*.py'):
  q=code/p.name
  if q.exists():assert sha(p)==sha(q),'Frozen initial code must not be changed: '+p.name
  else:shutil.copy2(p,q)
 save(NEW/'CODE_FINAL_MANIFEST.json',dict(unix=time.time(),files={p.name:sha(p) for p in code.glob('*.py')},initial_manifest_preserved=True))
 request=hostpath('C:/Users/HankL/.codex/attachments/9c6a1536-4e22-49b5-a561-ed64e8319692/已粘贴的文本.txt')
 shutil.copy2(request,NEW/'USER_REQUEST.txt');save(NEW/'USER_REQUEST_PROVENANCE.json',dict(source=str(request),sha256=sha(request)))
 (NEW/'REPRODUCTION.md').write_text('''# Reproduction and provenance

This is an offline oracle-stop package, not a trained model release. No training dataset, model weights, or new physics traces exist.

The scientific helpers use common.py's preserved WSL roots and the existing audit environment at /home/hank/envs/adaptive-online-rl-v1/bin/python. Windows delivery is a hash-verified readable mirror, not a standalone Windows runtime. NumPy/Matplotlib are used for rescoring/decomposition/figures.

register.py and suitability.py are one-time preregistration steps and intentionally reject post-gate reruns. Do not rerun them or overwrite PROTOCOL / initial SOURCE_AND_EVIDENCE. oracle.py, decomposition.py, metrics.py and plot.py describe the exact offline computation; a rerun should be directed to a fresh diagnostic directory if historical timestamp preservation is needed. verify.py checks preservation against the frozen baseline. report.py only formats completed evidence. deliver.py copies and hashes artifacts.

FULL_PLAN_ERROR_DECOMPOSITION.json retains all original outcome and raw trace paths and SHA256 hashes. Those sources remain read-only in the preserved V1/audit WSL directories; raw traces are not duplicated here. Future truth fields are diagnostic labels/metrics only. CAUSAL_INPUT_PROTOTYPES is a pre-fit feature audit, not a split training dataset.

STOP_DISPATCH is set. An independent new user-authorized package would be needed to reopen training or physics collection after the failed mandatory oracle gate.
''',encoding='utf-8')
 print('FINAL_CODE_AND_REQUEST_SAVED')
if __name__=='__main__':main()
