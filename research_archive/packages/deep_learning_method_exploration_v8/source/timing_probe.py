from pathlib import Path
import os,time,json,resource
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
P=Path(__file__).resolve().parents[1];m=json.loads((P/'analysis/FROZEN_BRANCH_MODEL.json').read_text());X=np.array([[1.,r['delta']] for r in m['training']]);Y=np.array([[r['phi'],r['relative_rate']] for r in m['training']]);a=time.perf_counter();c=np.linalg.lstsq(X,Y,rcond=None)[0];wall=time.perf_counter()-a
l=P/'runtime/output/LIFECYCLE_36283.jsonl';rr=[json.loads(s) for s in l.read_text().splitlines()] if l.exists() else [];archives=[dict(pid=r['pid'],bytes=r['bytes'],wall_s=r['unix']-r['begin_unix']) for r in rr if r['stage']=='ARCHIVE_END'];rows=[]
for f in (P/'attempts').glob('*_RESULT.json'):
 r=json.loads(f.read_text())
 if r.get('complete'):rows.append(dict(id=r['id'],wall_s=r['wall_s'],native_steps=r['actual_new_native_steps'],end_to_end_native_steps_per_wall_s=r['actual_new_native_steps']/r['wall_s']))
out=dict(local_affine_fit_wall_s=wall,identical_coefficients_max_error=float(np.max(abs(c-np.array(m['coefficients'])))),fresh_server_branch_timings=rows,archive_timings=archives,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,note='Fresh measured full branch wall includes physics, archive and metrics. Throughput is end-to-end, not a pure mj_step microbenchmark. Fit probe is one repeat of the same frozen calculation, not new data/model selection.')
(P/'analysis/FRESH_SERVER_TIMINGS.json').write_text(json.dumps(out,indent=2)+'\n');print('FIT_WALL',wall,'PHYSICAL_BRANCHES',len(rows),'ARCHIVES',len(archives))
