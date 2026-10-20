"""The frozen evaluator with bounded logging allocation and explicit teardown evidence."""
from common import *
import evaluate
from sac_env import rt
from operational_memory_v3 import install,phase,evidence,descendants
def main():
 install(rt)
 phase('EVALUATION_PHYSICS');evidence('EVALUATION_CHILD_START',request=sys.argv[1])
 try:
  evaluate.run(json.loads(Path(sys.argv[1]).read_text()))
 finally:
  phase('EVALUATION_CHILD_EXIT');evidence('EVALUATION_CHILD_FINAL',descendants=descendants(os.getpid()))
if __name__=='__main__':main()
