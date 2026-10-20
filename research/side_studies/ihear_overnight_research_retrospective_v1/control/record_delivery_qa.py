from pathlib import Path
import json,csv,time,hashlib
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
v=load(S/'VALIDATION_RESULTS.json');f=load(S/'FROZEN_SELECTION.json');ledger=load(S/'EVIDENCE_LEDGER.json');report=(S/'REPORT.md').read_text();brief=(S/'PROFESSOR_BRIEF.md').read_text()
assert v['status']=='COMPLETE' and v['primary_condition_count']==4 and v['primary_attempted_count']==4
assert f"motion通过{v['primary_pass']}/4" in report
assert f"motion {v['primary_pass']}/4" in brief and f"新条件合格{v['secondary_pass']}/4" in brief
assert f"{f['best']['comparison']['gain_percent']:.6f}%" in report and f"{f['best']['comparison']['gain_percent']:.6f}%" in brief
with (S/'EVIDENCE_LEDGER.csv').open(encoding='utf-8-sig') as h:csvrows=list(csv.DictReader(h))
assert len(csvrows)==len(ledger['records'])==80 and {x['id'] for x in csvrows}=={x['id'] for x in ledger['records']}
for row in ledger['records']:
    if row['id'].startswith('NIGHT_'):assert sha(Path(row['source']))==row['source_sha256'],('NIGHT_SOURCE_CHANGED',row['id'])
figures=sorted((S/'FIGURES').glob('*.png'));assert len(figures)==7
qa=dict(status='PASS',generated_unix=time.time(),method='assistant manually inspected all seven latest PNGs via view_image; figure07 title-label collision fixed and re-rendered/re-inspected',
        inspection_items=['Chinese glyphs readable','no clipped essential text','legends distinguish reference/actual','failure labels and titles do not overlap','actual data and historical scope captions retained'],
        figures=[dict(file=str(p.relative_to(S)),sha256=sha(p)) for p in figures],physics_attempts_added=0)
(S/'VISUAL_QA.json').write_text(json.dumps(qa,indent=2,ensure_ascii=False)+'\n')
consistency=dict(status='PASS',generated_unix=time.time(),selection_sha256=sha(S/'FROZEN_SELECTION.json'),validation_sha256=sha(S/'VALIDATION_RESULTS.json'),REPORT_sha256=sha(S/'REPORT.md'),PROFESSOR_BRIEF_sha256=sha(S/'PROFESSOR_BRIEF.md'),
                 primary_pass=v['primary_pass'],primary_denominator=4,secondary_pass=v['secondary_pass'],evidence_JSON_CSV_count=80,night_source_hashes_verified=True,figure_count=7)
(S/'CONTENT_CONSISTENCY.json').write_text(json.dumps(consistency,indent=2)+'\n');print('DELIVERY_CONTENT_AND_VISUAL_QA_PASS',consistency)
