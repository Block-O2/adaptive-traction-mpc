from pathlib import Path
import json,hashlib,os,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1')
old=json.loads((P/'FROZEN_18D.json').read_text());C=json.loads((P/'CANDIDATE.json').read_text());R=json.loads((P/'BOUNDED_REPAIR.json').read_text());mapping=json.loads((P/'PARAMETER_MAP.json').read_text());scales=np.asarray([x['scale'] for x in mapping['parameters']]);rows=[]
for name,c in [('E',old),('C',C),('R',R)]:
 x=np.asarray(c['free_parameters']);n=np.asarray(c['normalized_parameters']);assert x.shape==(18,) and np.all(np.isfinite(x));assert np.all(abs(n)<=1+1e-12);assert np.max(abs(n*scales-x))<1e-16
 assert c['phases']==old['phases']
 rows.append(dict(name=name,id=c['id'],sha256=hashlib.sha256((P/('FROZEN_18D.json' if name=='E' else 'CANDIDATE.json' if name=='C' else 'BOUNDED_REPAIR.json')).read_bytes()).hexdigest(),changed_indices=np.flatnonzero(x!=old['free_parameters']).tolist(),normalized_scale_max_error=float(np.max(abs(n*scales-x))),RETURN_plateau_identity=True))
for i in range(18):assert C['free_parameters'][i]==(0. if i in [3,4,13] else old['free_parameters'][i])
out=dict(status='PASS',unix=time.time(),rows=rows,inheritance_note='candidate.parameters.source/changes and seed_family retain historical RETURN plateau provenance. They are not the new velocity intervention description; that is candidate id plus this exact delta and SELECTED_IMPROVEMENT.',new_physics=0)
(P/'audit/PARAMETER_REPRESENTATION.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
print('PARAMETER_REPRESENTATION_PASS')
