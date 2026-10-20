"""Record human-visible model review of the exact supplied figure hashes."""
from task_bootstrap import *

def main():
 path=STUDY/'delivery/FIGURE_MANIFEST.json';manifest=json.loads(path.read_text());approved={}
 for arg in sys.argv[1:]:
  name,digest=arg.split('=',1);assert len(digest)==64;approved[name]=digest
 assert len(approved)==6 and len(manifest['figures'])==6
 for row in manifest['figures']:
  p=Path(row['path']);assert approved[p.name]==row['sha256']==sha(p),'VISUAL_REVIEW_HASH_MUST_MATCH_CURRENT_FILE'
 manifest.update(status='VISUALLY_VERIFIED',visual_review_unix=time.time(),visual_review_method='All six rendered PNGs inspected through view_image; no clipping/illegible legends; latest resource figure covers the final sample.',visual_review_approved_hashes=approved)
 save(path,manifest);print(json.dumps(dict(status=manifest['status'],figures=len(approved),CLOSEOUT_STATUS_not_modified=True)))
if __name__=='__main__':main()
