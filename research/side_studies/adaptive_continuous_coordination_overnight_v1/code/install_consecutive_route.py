from task_bootstrap import *
import ast
def main():
 p=STUDY/'code/worker.py';text=p.read_text();needle="  try:\n"
 old="  try:" # main try has one leading space, not two
 old=" try:\n   from study_common" if " try:\n   from study_common" in text else " try:\n  from study_common"
 assert old in text
 text=text.replace(old," if request.get('mode')=='consecutive':\n  from consecutive_worker import run_many\n  run_many(request);return\n"+old,1);ast.parse(text);p.write_text(text);print('COUNTED_SAME_PROCESS_REPETITION_ROUTE_READY')
if __name__=='__main__':main()
