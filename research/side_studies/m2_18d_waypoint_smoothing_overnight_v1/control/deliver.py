from pathlib import Path
import json,hashlib,shutil,re,xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
execution=json.loads((P/'EXECUTION_CODE_MANIFEST.json').read_text())['files']
for f in (L/'control').glob('*.py'):
 key='control/'+f.name
 if key in execution:assert sha(f)==execution[key],('Immutable executed source differs',key)
 shutil.copy2(f,P/'control'/f.name)
for f in (P/'control').glob('*.py'):compile(f.read_text(),str(f),'exec')
report=(P/'REPORT.md').read_text();links=re.findall(r'\]\(([^)]+)\)',report);local_links=[s for s in links if not s.startswith(('http','/'))];missing=[s for s in local_links if not (P/s).exists()];assert not missing,missing
for f in (P/'figures').glob('*.png'):
 with Image.open(f) as im:im.verify()
for f in (P/'figures').glob('*.svg'):ET.parse(f)
rows=json.loads((P/'TARGETED_RESULTS.json').read_text())['rows'];verified=[]
for r in rows:
 if r['status']!='COMPLETE':continue
 z=np.load(P/'series'/(r['id']+'.npz'));cf=np.r_[0,np.cumsum(z['f'][:-1]*np.diff(z['tf']))];assert np.array_equal(cf,z['cf']);assert abs(cf[-1]-r['J_F'])<1e-8
 verified.append(r['id'])
manifest={str(f.relative_to(P)):sha(f) for f in (P/'control').glob('*.py')};(P/'ANALYSIS_CODE_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
(P/'audit/DELIVERY_QA.json').write_text(json.dumps(dict(status='PASS',all_report_links_exist=True,png_svg_parse=True,cumulative_force_recomputed=verified,physical_step_added=0,visual_qa='Core/local/contrast figure visual inspection is separately recorded after Windows mirror export.'),indent=2))
dirs=['audit','control','derived','figures','series','reports','provenance','logs','EXECUTION','evidence','output']
for d in dirs:
 if (P/d).exists():shutil.copytree(P/d,L/d,dirs_exist_ok=True)
for f in P.iterdir():
 if f.is_file() and f.suffix in ['.md','.json','.jsonl','.html']:shutil.copy2(f,L/f.name)
files={str(f.relative_to(L)):dict(size=f.stat().st_size,sha256=sha(f)) for f in L.rglob('*') if f.is_file() and f.name not in ['REVIEW_MIRROR_MANIFEST.json','core_preview.png']}
(L/'REVIEW_MIRROR_MANIFEST.json').write_text(json.dumps(dict(canonical=str(P),raw_and_source_closure_canonical_only=True,files=files),indent=2))
print('DELIVERY_QA_AND_MIRROR_PASS',len(files),'files','completed_candidate_curves',len(verified))
