"""Portable read-only SHA256 verification. No dependencies, physics or file writes."""
from pathlib import Path
import json,hashlib,sys
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text(encoding='utf-8'))
def sha(f):
    h=hashlib.sha256()
    with f.open('rb') as s:
        for b in iter(lambda:s.read(4*2**20),b''):h.update(b)
    return h.hexdigest()
def main():
    seal=read('DELIVERY_SEAL.json');manifest=read('EVIDENCE_MANIFEST.json');errors=[]
    assert sha(P/'EVIDENCE_MANIFEST.json')==seal['manifest_sha256'],'MANIFEST_CHANGED'
    assert sha(P/'REPORT.md')==seal['report_sha256'],'REPORT_CHANGED'
    assert sha(P/'PACKAGE_VERIFICATION.json')==seal['package_verification_sha256'],'VERIFICATION_CHANGED'
    for rel,record in manifest['files'].items():
        f=(P/rel).resolve();assert f.is_relative_to(P),'MANIFEST_PATH_OUTSIDE_PACKAGE'
        if not f.is_file():errors.append(dict(path=rel,reason='MISSING'));continue
        if f.stat().st_size!=record['size'] or sha(f)!=record['sha256']:errors.append(dict(path=rel,reason='CONTENT_CHANGED'))
    a=read('ATTEMPT_ACCOUNTING.json');assert a['starts']==a['ends']<=80 and not a['open_starts'] and not a['unmatched_ends']
    assert read('STATE.json')['phase']=='STOP' and read('PHYSICS_STOP.json')['status']=='STOP'
    assert read('PACKAGE_VERIFICATION.json')['status']=='PASS'
    print(json.dumps(dict(status='FAIL' if errors else 'PASS',files=len(manifest['files']),bytes=sum(r['size'] for r in manifest['files'].values()),
        starts=a['starts'],ends=a['ends'],errors=errors,read_only=True,new_physics_starts=0),indent=2,ensure_ascii=False))
    if errors:sys.exit(1)
if __name__=='__main__':main()
