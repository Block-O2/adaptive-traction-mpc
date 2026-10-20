from task_bootstrap import *
import ast
def main():
 p=STUDY/'code/worker.py';text=p.read_text();old="   if request.get('timing_version','T0').startswith('E3') and request.get('method')!='M0':"
 new="   if request.get('timing_version','T0').startswith('E5') and request.get('method')!='M0':\n    from async_native_main import AsyncNativeInterface\n    interface=AsyncNativeInterface(request)\n   elif request.get('timing_version','T0').startswith('E3') and request.get('method')!='M0':"
 assert old in text;text=text.replace(old,new);ast.parse(text);p.write_text(text);print('EXISTING_NATIVE_TASK_WORKER_M2_INTEGRATION_READY')
if __name__=='__main__':main()
