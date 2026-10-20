from task_bootstrap import *
import ast
def main():
 p=STUDY/'code/worker.py';text=p.read_text()
 old="interface=PrefixBInterface(request) if request.get('method')=='M0' else NativeInterface(request)"
 new="if request.get('timing_version','T0')!='T0' and request.get('method')!='M0':\n    from optimized_method import OptimizedNativeInterface\n    interface=OptimizedNativeInterface(request)\n   else:interface=PrefixBInterface(request) if request.get('method')=='M0' else NativeInterface(request)"
 assert text.count(old)==1;text=text.replace(old,new);ast.parse(text);p.write_text(text)
 save(STUDY/'CODE_MANIFEST.json',{str(p):sha(p) for p in sorted((STUDY/'code').glob('*.py'))})
 print('VERSIONED_E1_WORKER_INSTALLED')
if __name__=='__main__':main()
