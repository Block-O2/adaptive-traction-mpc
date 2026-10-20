"""Retain exact declared actor bytes in compact delivery, no control edits."""
from task_bootstrap import *
def main():
 audit=json.loads((STUDY/'reports/SOURCE_CLOSURE_AUDIT.json').read_text());assert not audit['issues'] and audit['unretained_declared_sources']==0
 rows={};references=[]
 for run in audit['rows']:
  for source in run['declared_sources']:
   expected=source['declared_sha256'];original=Path(source['retained_byte_copies'][0]);rel=Path('historical_code')/expected/original.name;target=STUDY/'delivery'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(original,target);assert sha(target)==expected
   rows[str(rel)]=dict(relative_path=str(rel),sha256=expected,bytes=target.stat().st_size,retained_from=str(original));references.append(dict(id=run['id'],declared_path=source['path'],declared_sha256=expected,delivery_relative_path=str(rel)))
 out=dict(status='EXACT_DECLARED_ACTOR_BYTES_RETAINED',files=list(rows.values()),attempt_references=references,total_bytes=sum(r['bytes'] for r in rows.values()),source_closure_report_sha256=sha(STUDY/'reports/SOURCE_CLOSURE_AUDIT.json'),limitation=audit['runtime_attestation_limit'])
 save(STUDY/'delivery/ACTOR_SOURCE_RETENTION_MANIFEST.json',out);print(json.dumps(dict(status=out['status'],files=len(rows),attempt_references=len(references),bytes=out['total_bytes'])))
if __name__=='__main__':main()
