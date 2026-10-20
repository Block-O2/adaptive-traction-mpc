from stream_runtime_evidence import *
from inspect_schema import tree
def main():
 id=sys.argv[1];key=sys.argv[2]
 for i,row in enumerate(array_items(STUDY/'source/results'/id/'runtime_artifacts.json.gz',key)):
  if i>=2:return
  print(json.dumps(tree(row)))
if __name__=='__main__':main()
