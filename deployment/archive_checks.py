#!/usr/bin/env python3
"""Read-only archive identity, source syntax, public-content and documentation checks.

Reports paths/rule names only for potential secrets; never prints matching values.
Historical Markdown links are records, not promised live portable interfaces.
"""
from pathlib import Path
import argparse, ast, hashlib, json, re, subprocess
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
DOCS=["README.md","SYSTEM_ARCHITECTURE.md","TRADITIONAL_CONTROL.md","LEARNING_ARCHITECTURE.md","LEARNING_METHODS_HISTORY.md","EXPERIMENTAL_EVIDENCE.md","FAILURE_ANALYSIS.md","REPRODUCTION_GUIDE.md","NEXT_GENERATION_ARCHITECTURE.md","PROFESSOR_TECHNICAL_BRIEF.md","ARCHIVE_MANIFEST.md","ARCHIVE_VERIFICATION.md","DELETION_IMPACT.md","FINAL_HANDOFF.md"]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 assert not a.output.exists(),'Preserve existing verification reports'
 rows=json.loads((ROOT/'research_archive/manifests/selected_files.json').read_text())['files']
 bad=[]
 for row in rows:
  p=ROOT/row['archive']
  if not p.is_file() or p.is_symlink() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:bad.append(row['archive'])
 link_issues=[];links=0
 for name in DOCS:
  p=ROOT/name
  if not p.is_file():link_issues.append(dict(document=name,target='MISSING_DOCUMENT'));continue
  for s in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text()):
   s=s.strip().split(' "')[0].strip('<>')
   if re.match(r'^[a-zA-Z]+:',s) or s.startswith('#'):continue
   target=unquote(s.split('#')[0])
   if not target:continue
   links+=1
   if not (p.parent/target).exists():link_issues.append(dict(document=name,target=target))
 tracked=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z']).decode().split('\0')
 paths=set(x for x in tracked if x)|{x['archive'] for x in rows}|{x for x in DOCS if (ROOT/x).is_file()}
 patterns={'private_key':rb'-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----','github_token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})','aws_key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b','openai_token':rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{30,}','credential_url':rb'https?://[^\s/@:]+:[^\s/@]{8,}@','slack_token':rb'\bxox[baprs]-[A-Za-z0-9-]{20,}'}
 findings=[];syntax=[];seen=set();scanned=0;py=0;false_positives=[]
 allow=json.loads((ROOT/"research_archive/manifests/public_review_allowlist.json").read_text())["files"]
 for name in sorted(paths):
  p=ROOT/name
  if not p.is_file() or p.is_symlink():continue
  b=p.read_bytes();digest=hashlib.sha256(b).digest()
  if digest in seen:continue
  seen.add(digest)
  if b'\0' in b[:8192]:continue
  scanned+=1
  for rule,pattern in patterns.items():
   if re.search(pattern,b):
    reviewed=next((x for x in allow if x['path']==name and x['rule']==rule and x['sha256']==hashlib.sha256(b).hexdigest()),None)
    if reviewed:false_positives.append(reviewed)
    else:findings.append(dict(path=name,rule=rule))
  if p.suffix=='.py':
   py+=1
   try:ast.parse(b,filename=name)
   except (SyntaxError,ValueError) as e:syntax.append(dict(path=name,error=str(e)))
 report=dict(schema='ihear.archive.static_verification.v1',selected_files=len(rows),selected_identity_errors=bad,curated_documents=len(DOCS),local_markdown_links_checked=links,curated_link_errors=link_issues,unique_text_blobs_reviewed=scanned,high_confidence_secret_findings=findings,reviewed_false_positives=false_positives,unique_python_blobs_parsed=py,python_syntax_findings=syntax,public_review_limit='Pattern scan and selected-path review; no guarantee of exhaustive historical secret detection. Archived synthetic scientific simulation, no claim of hardware/clinical validation.',status='PASS' if not (bad or link_issues or findings or syntax) else 'FAIL')
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print(json.dumps(report,ensure_ascii=False))
 raise SystemExit(report['status']!='PASS')
if __name__=='__main__':main()
