from common import *
def main():
 assert read(NEW/'FINAL_STATUS.json')['STOP'] and read(NEW/'PRESERVATION_AND_VERIFICATION.json')['status']=='PASS'
 dst=LOCAL/'deliverables';dst.mkdir(exist_ok=True)
 records={}
 for p in sorted(NEW.rglob('*')):
  if not p.is_file():continue
  q=dst/p.relative_to(NEW);q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
  assert sha(p)==sha(q);records[str(q.relative_to(dst))]=dict(sha256=sha(q),bytes=q.stat().st_size,source=str(p))
 save(dst/'DELIVERY_MANIFEST.json',dict(status='PASS',unix=time.time(),files=records,raw_traces='Not duplicated; original WSL outcome/trace paths and hashes in FULL_PLAN_ERROR_DECOMPOSITION.json'))
 print(json.dumps(dict(status='DELIVERED_HASH_VERIFIED',files=len(records),destination=str(dst))))
if __name__=='__main__':main()
