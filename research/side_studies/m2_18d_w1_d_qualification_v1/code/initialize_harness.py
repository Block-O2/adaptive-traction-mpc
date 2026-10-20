from task_bootstrap import *
import ast
def main():
 for name in ('runner.py','accounting.py'):
  text=(BASE/'code'/name).read_text().replace(str(BASE),str(STUDY)).replace('240','160')
  if name=='runner.py':text=text.replace("filename='RESOURCES.jsonl'","filename='RESOURCE_LOG.jsonl'")
  ast.parse(text);(STUDY/'code'/name).write_text(text)
 p=STUDY/'code/worker.py';text=p.read_text().replace('call_audit.install()','call_audit.install()\n  import profiling_instrumentation as profile\n  profile.install()')
 text=text.replace("path=Path(request['result_path'])","if 'profile' in locals():save(request['id']+'_TIMING_PROFILE.json',profile.evidence())\n path=Path(request['result_path'])")
 ast.parse(text);p.write_text(text)
 save(STUDY/'CODE_MANIFEST.json',{str(p):sha(p) for p in sorted((STUDY/'code').glob('*.py'))})
 print('DURABLE_TIMING_HARNESS_READY')
if __name__=='__main__':main()
