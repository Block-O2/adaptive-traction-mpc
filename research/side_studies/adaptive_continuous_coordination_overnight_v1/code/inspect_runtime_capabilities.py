from task_bootstrap import *
import importlib.util,shutil
def main():
 out=dict(python=sys.version,executable=sys.executable,modules={name:(None if importlib.util.find_spec(name) is None else importlib.util.find_spec(name).origin) for name in ['numba','Cython','scipy','numpy']},compiler_tools={name:shutil.which(name) for name in ['gcc','g++','cython']},no_installation=True,no_physics=True)
 save(STUDY/'reports/LOCAL_NUMERICAL_RUNTIME_CAPABILITIES.json',out);print(json.dumps(out))
if __name__=='__main__':main()
