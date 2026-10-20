from task_bootstrap import *
import ast
LOCAL=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1')
def main():
 manifest=STUDY/'CODE_MANIFEST.json'
 if manifest.exists():
  archive=STUDY/'code_history'/sha(manifest)
  if not archive.exists():shutil.copytree(STUDY/'code',archive/'code');shutil.copy2(manifest,archive/'CODE_MANIFEST.json')
 for p in LOCAL.glob('*.py'):
  if p.name=='bootstrap_study.py':continue
  ast.parse(p.read_text());shutil.copy2(p,STUDY/'code'/p.name)
 save(manifest,{str(p):sha(p) for p in sorted((STUDY/'code').glob('*.py'))})
 print('SYNC_OK')
if __name__=='__main__':main()
