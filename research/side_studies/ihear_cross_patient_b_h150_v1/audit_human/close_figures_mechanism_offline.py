"""Last offline source/output binding and immutable final figure snapshot."""
from pathlib import Path
import argparse,hashlib,json,shutil
from datetime import datetime,timezone

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--mirror',type=Path,required=True);args=ap.parse_args();p=args.package;mirror=args.mirror;checks=[]
 def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
 def check(name,passed):
  assert passed,name
  checks.append(name)
 fm=json.loads((p/'figures/FIGURE_MANIFEST.json').read_text());mm=json.loads((p/'audit_human/FAILURE_MECHANISM_INPUTS.json').read_text());me=json.loads((p/'audit_human/MECHANISM_EVIDENCE_FINAL.json').read_text())
 for label,manifest,field in [('figure',fm,'source_inputs'),('mechanism synthesis',mm,'sources'),('mechanism extraction',me,'sources')]:
  for rel,entry in manifest[field].items():check(label+' source '+rel,sha(p/rel)==entry['sha256'])
 for row in fm['figures']:check('figure output '+row['file'],sha(p/'figures'/row['file'])==row['sha256'])
 check('renderer hash',sha(p/'make_cross_figures.py')==fm['code_sha256'])
 check('report hash',sha(p/'FAILURE_MECHANISM_REPORT.md')==mm['report_sha256'])
 check('report generator hash',sha(p/'audit_human/build_failure_mechanism_report.py')==mm['producer_code_sha256'])
 check('mechanism snapshot hash',sha(p/'audit_human/MECHANISM_EVIDENCE_FINAL.json')==mm['mechanism_snapshot_sha256'])
 check('final counts',fm['patient_count']==12 and fm['complete_valid_pair_count']==10 and fm['fully_qualified_h150_count']==8)
 check('motion failures',mm['motion_failed']==['P05','P08'])
 check('partial failures',mm['partial_H150']==['P06','P10'])
 check('first registered motion failure figure',next(x for x in fm['figures'] if x['file']=='06_terminal_timeline.png')['selected_patient']=='P05')
 snap=p/'audit_figures/v4_FINAL_ALL12';check('new versioned snapshot',not snap.exists());(snap/'images').mkdir(parents=True)
 for row in fm['figures']:shutil.copy2(p/'figures'/row['file'],snap/'images'/row['file'])
 shutil.copy2(p/'figures/FIGURE_MANIFEST.json',snap/'FIGURE_MANIFEST.json');shutil.copy2(p/'audit_human/QA_v4_FINAL_ALL12.md',snap/'QA.md')
 check('pinned final figure manifest',sha(snap/'FIGURE_MANIFEST.json')=='4cf69e596a6dcecd0254cd01a5b00ba6325cb9e1070d49f0ac756c02a063011d')
 out={'schema':'IHEAR_FINAL_FIGURE_MECHANISM_QA_V1','status':'PASS','generated_utc':datetime.now(timezone.utc).isoformat(),'physics_starts':0,'all_12_owners_joined':True,'complete_valid_pairs':10,'fully_qualified_H150':8,'check_count':len(checks),'checks':checks,'figure_manifest_sha256':sha(snap/'FIGURE_MANIFEST.json'),'mechanism_report_sha256':mm['report_sha256'],'mechanism_inputs_sha256':sha(p/'audit_human/FAILURE_MECHANISM_INPUTS.json'),'scope':'Offline source/output binding and visually reviewed final scientific figures. Scientific failures remain failures.','subagent_writers_closed_after_this_call':True}
 f=p/'audit_human/FINAL_FIGURE_MECHANISM_QA.json';f.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
 shutil.copytree(snap,mirror/'audit_figures'/snap.name)
 for f in [p/'FAILURE_MECHANISM_REPORT.md',p/'audit_human/MECHANISM_EVIDENCE_FINAL.json',p/'audit_human/FAILURE_MECHANISM_INPUTS.json',p/'audit_human/FINAL_FIGURE_MECHANISM_QA.json']:
  dest=mirror/f.relative_to(p);shutil.copy2(f,dest);assert sha(f)==sha(dest)
 print(json.dumps({k:v for k,v in out.items() if k!='checks'}))

if __name__=='__main__':main()
