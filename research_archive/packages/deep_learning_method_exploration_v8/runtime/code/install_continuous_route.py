from task_bootstrap import *
import ast
def main():
 p=STUDY/'code/worker.py';s=p.read_text();old="  from consecutive_worker import run_many\n  run_many(request);return"
 new="  if request.get('continuous_session'):\n   from continuous_worker import run_many\n  else:\n   from consecutive_worker import run_many\n  run_many(request);return"
 assert old in s;s=s.replace(old,new,1);ast.parse(s);p.write_text(s);print('NATIVE_CONTINUOUS_SCI_ROUTE_INSTALLED')
if __name__=='__main__':main()
