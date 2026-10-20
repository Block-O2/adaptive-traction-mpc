"""Bind the six figures visually reviewed by root to the canonical final bytes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,shutil
P=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
manifest=json.loads((P/'figures/FIGURE_MANIFEST.json').read_text())
review=Path(json.loads((P/'ENVIRONMENT.json').read_text())['review'])
assert manifest['patient_count']==12 and manifest['complete_valid_pair_count']==10
assert len(manifest['figures'])==6
out=P/'audit_figures/root_final_review';out.mkdir(parents=True,exist_ok=True)
rows=[]
for row in manifest['figures']:
    original=P/'figures'/row['file'];viewed=review/'figures'/row['file']
    assert sha(original)==row['sha256']==sha(viewed),row['file']
    rows.append(dict(file=row['file'],sha256=row['sha256'],canonical_equals_visually_reviewed_mirror=True))
    shutil.copy2(original,out/row['file'])
shutil.copy2(P/'figures/FIGURE_MANIFEST.json',out/'FIGURE_MANIFEST.json')
notes=[
 'Root directly inspected all six rendered PNGs in view_image, including text, axes, legends, extrema, and final denominators.',
 'No material clipping, unreadable overlap, misleading missing-as-zero value, or incorrect final qualification marker found.',
 'Twelve identities retained; ten complete pairs; eight fully qualified; P05/P08 motion failures; P06/P10 absent full H150 metrics.',
 'Figure05 marks incomplete-arm safety PASS with prefix-only asterisk; figure06 uses actual P05 RETURN elapsed and includes both physical minima and actual reference.',
 'Figure06 terminal window is explicitly not claimed to locate the OUTBOUND motion failures.',
 'Figure04 retains force benefit alongside moment and joint-specific tracking costs.',
 'All figures use PHYSICAL_LEVEL1 simulation scope without clinical or statistical-generalization claims.',
 'Root completed final review after the delegated reviewer was interrupted for closure; no unfinished visual correction was identified.'
]
result=dict(status='PASS',reviewer='root_direct_visual_inspection',generated_utc=datetime.now(timezone.utc).isoformat(),
    figures=rows,notes=notes,final_manifest_sha256=sha(P/'figures/FIGURE_MANIFEST.json'),physics_starts=0)
(out/'QA.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
(out/'QA.md').write_text('# 最终六图目视复核\n\n状态：PASS。根协调器已直接查看六张最终 PNG，并核实所查看 Windows 镜像与 canonical 图片逐字节一致。\n\n'+
    '\n'.join('- '+n for n in notes)+'\n',encoding='utf-8')
print('FINAL_SIX_FIGURE_VISUAL_REVIEW_BOUND',len(rows))
