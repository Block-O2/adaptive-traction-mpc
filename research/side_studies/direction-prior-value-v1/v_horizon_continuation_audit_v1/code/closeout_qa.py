"""Read-only verification of the frozen online algorithm and fit metrics."""
from freeze import *

def main():
 contracts={}
 for path in sorted(STUDY.glob('COMPARISON_v*.json')):
  data=json.loads(path.read_text());sources=data.get('algorithm_sources',{})
  if sources:
   mismatches=[name for name,expected in sources.items() if sha(Path(name))!=expected]
   assert not mismatches,(path.name,mismatches)
   contracts[path.name]=dict(source_count=len(sources),all_current_hashes_match=True)
 save(STUDY/'FROZEN_ALGORITHM_VERIFICATION.json',dict(status='PASS',contracts=contracts))
 for path in sorted(STUDY.glob('weights_v*/TRAINING.json')):
  data=json.loads(path.read_text())
  print(json.dumps(dict(directory=path.parent.name,metrics=data.get('metrics'),timing={k:v for k,v in data.items() if any(word in k for word in ('wall','peak','error','consistency'))})))
 print(json.dumps(dict(status='FROZEN_ALGORITHM_PASS',contracts=contracts)))

if __name__=='__main__':main()
