from task_bootstrap import *
import ast
def main():
 history=STUDY/'code_history';history.mkdir(exist_ok=True)
 if (STUDY/'CODE_MANIFEST.json').exists():
  dst=history/sha(STUDY/'CODE_MANIFEST.json')
  if not dst.exists():
   dst.mkdir();shutil.copy2(STUDY/'CODE_MANIFEST.json',dst/'CODE_MANIFEST.json');shutil.copytree(STUDY/'code',dst/'code')
 for p in LOCAL.glob('*.py'):
  ast.parse(p.read_text());shutil.copy2(p,STUDY/'code'/p.name)
 save(STUDY/'CODE_MANIFEST.json',{str(p):sha(p) for root in (STUDY/'code',STUDY/'deps') for p in root.glob('*.py')})
 print('SYNC_OK')
if __name__=='__main__':main()
