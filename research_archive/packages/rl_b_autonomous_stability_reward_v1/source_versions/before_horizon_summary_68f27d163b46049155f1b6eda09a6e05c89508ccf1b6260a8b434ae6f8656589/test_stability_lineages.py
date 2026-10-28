"""Engineering-only fixtures; never add fabricated rows to physical evidence."""
from pathlib import Path
import json
from research_common import ROOT,atomic,now,sha
from stability_lineages import resolve,retained,latest_mean
seeds=[1495656323,1630784693]
def row(seed,branch,endpoint,success=True):
    return dict(seed=seed,branch=branch,index=endpoint+1,success=success,mode='evaluation',policy_mode='deterministic',job_id=f'{branch}_{seed}_{endpoint}',parent=f'{branch}/{seed}/{endpoint}')
base=[row(s,'H2_AGG64',30) for s in seeds]
tail=[row(s,'RETENTION_H2',60,s==seeds[0]) for s in seeds]
mapping={'RETENTION_H2':'H2_AGG64'}
metas={}
for x in base+tail:
    b=x['branch'];s=x['seed']
    metas[x['parent']]=dict(seed=s,branch=b,continuation_episodes=x['index']-1,parent=f'H2_AGG64/{s}/30',
        research_config=dict(seed=s,branch=b,learning_rate=0.0003,rollout='aggregate64',reward='R0',target_kl=None))
load=lambda p:metas[p]
checks={}
r=resolve(base+tail,mapping,load)
checks['later_failure_removes_uniform_retention']=r['status']=='PASS' and not retained(r['groups'],seeds)
for x in tail:x['success']=True
r=resolve(base+tail,mapping,load)
checks['both_later_successes_join_original_lineage']=retained(r['groups'],seeds)==['H2_AGG64'] and len(r['groups']['H2_AGG64'])==4
comparison=[dict(lineage='H2_AGG64',seed=seeds[0],mode='deterministic',continuation_endpoint=n,JF_relative_percent=p) for n,p in [(30,-1),(60,1)]]
checks['latest_dose_cannot_reuse_earlier_gain']=latest_mean(comparison,'H2_AGG64',seeds[0])['JF_relative_percent']==1
metas[tail[0]['parent']]['research_config']['learning_rate']=0.0001
checks['method_change_rejected']=resolve(base+tail,mapping,load)['status']=='REVIEW_REQUIRED'
checks['undeclared_retention_rejected']=resolve(tail,{},load)['status']=='REVIEW_REQUIRED'
actual=[json.loads(x) for x in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
r=resolve(actual,{})
raw={b:[x for x in actual if x['branch']==b] for b in {x['branch'] for x in actual}}
checks['current_actual_results_unchanged_without_aliases']=r['status']=='PASS' and sorted(retained(r['groups'],seeds))==sorted(retained(raw,seeds))
result=dict(time_utc=now(),status='PASS' if all(checks.values()) else 'FAIL',checks=checks,
    actual_retained=retained(r['groups'],seeds),physical_attempts=0,optimizer_updates=0,
    fixture_scope='In-memory synthetic metadata and rows only; no scientific log writes',source_sha256=sha(ROOT/'scripts/stability_lineages.py'))
atomic(ROOT/'audit/STABILITY_LINEAGE_ENGINEERING_TEST.json',result)
print(json.dumps(result));assert all(checks.values())
