from pathlib import Path
import json,hashlib,shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_waypoint_smoothing_overnight_v1');L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name
record=dict(status='PASS',inspected=['01_core_common_timeline.png','06_R_targeted_intervention.png','08_local_motion_force_contrast.png'],repairs='Local plot y limits now use visible time-window data; contrast annotation stays within plot. Core phase labels sit inside force panel; absolute axis remains separate. No metric, qualification or physical result changed.',scope='Same-agent visual inspection of rendered PNGs; SVG/PNG structural checks separately recorded.')
(P/'audit/VISUAL_QA.json').write_text(json.dumps(record,indent=2));shutil.copy2(P/'audit/VISUAL_QA.json',L/'audit/VISUAL_QA.json')
shutil.copy2(__file__,P/'control/record_visual_qa.py')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
code={str(f.relative_to(P)):sha(f) for f in (P/'control').glob('*.py')};(P/'ANALYSIS_CODE_MANIFEST.json').write_text(json.dumps(code,indent=2));shutil.copy2(P/'ANALYSIS_CODE_MANIFEST.json',L/'ANALYSIS_CODE_MANIFEST.json')
m=json.loads((L/'REVIEW_MIRROR_MANIFEST.json').read_text())
for n in ['audit/VISUAL_QA.json','ANALYSIS_CODE_MANIFEST.json','control/record_visual_qa.py']:
 f=L/n;m['files'][n]=dict(size=f.stat().st_size,sha256=sha(f))
(L/'REVIEW_MIRROR_MANIFEST.json').write_text(json.dumps(m,indent=2));print('VISUAL_QA_RECORDED')
