from task_bootstrap import *
import inspect
def main():
 import study_common as sc
 env=sc.SACExpertEnv
 print('ENV_SOURCE',inspect.getfile(env))
 for name in ('__init__','close','boundary','_tick','episode_end'):
  if hasattr(env,name):print(name,inspect.getsource(getattr(env,name)))
 print('MEMBERS',[name for name in dir(env) if not name.startswith('__')])
if __name__=='__main__':main()
