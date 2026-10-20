"""Copy compact final evidence; raw unique physics evidence remains in WSL."""
from task_bootstrap import *

def main():
 assert json.loads((STUDY/'FINAL_STATUS.json').read_text())['status']=='COMPLETE_STOPPED'
 dst=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_learning_matrix_v1/deliverables');dst.mkdir(parents=True,exist_ok=True)
 chosen=list(STUDY.glob('*.json'))+list(STUDY.glob('*.md'))+list(STUDY.glob('*.csv'))+list(STUDY.glob('*.jsonl'))
 chosen += [p for p in (STUDY/'reports').rglob('*') if p.is_file()]
 chosen += [p for p in (STUDY/'weights').rglob('*') if p.is_file()]
 chosen += [STUDY/'output/RESOURCES.jsonl',STUDY/'output/RESOURCES_ALL_PROCESS_TREES.jsonl']
 chosen += [p for p in (STUDY/'output').glob('*_REPLAY_GATE.json')]
 chosen += [STUDY/'USER_REQUEST.txt']
 rows=[]
 for p in chosen:
  if not p.exists() or p.name=='DELIVERY_MANIFEST.json':continue
  q=dst/p.relative_to(STUDY);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);assert sha(p)==sha(q)
  rows.append(dict(path=str(p.relative_to(STUDY)),bytes=p.stat().st_size,sha256=sha(q)))
 manifest=dict(files=rows,total_bytes=sum(r['bytes'] for r in rows),authoritative_WSL_directory=str(STUDY),raw_results='source/results and output in authoritative WSL study; FINAL_MANIFEST.json retains every raw/source hash',copy_verified=True)
 save(dst/'DELIVERY_MANIFEST.json',manifest);save(STUDY/'DELIVERY_MANIFEST.json',manifest)
 print(json.dumps(dict(delivery=str(dst),files=len(rows),bytes=manifest['total_bytes'],report=str(dst/'FINAL_REPORT.md'))))
if __name__=='__main__':main()
