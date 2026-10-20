from audit_common import *
import ast
def main():
 previous=STUDY/'CODE_MANIFEST.json'
 if previous.exists():
  target=STUDY/'code_history'/sha(previous)
  if not target.exists():
   target.mkdir(parents=True);shutil.copy2(previous,target/'CODE_MANIFEST.json')
   for folder in ('code','deps'):shutil.copytree(STUDY/folder,target/folder)
 for p in LOCAL.glob('*.py'):
  ast.parse(p.read_text())
  if p.name=='bootstrap.py':continue
  shutil.copy2(p,STUDY/'code'/p.name)
 save(STUDY/'CODE_MANIFEST.json',{str(p):sha(p) for root in ('code','deps') for p in (STUDY/root).glob('*.py')})
 print('AUDIT_SCRIPTS_SYNCED')
if __name__=='__main__':main()
