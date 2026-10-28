"""Join verified continuation branches without losing earlier or later failures."""
from collections import defaultdict
from pathlib import Path
import json

BOOKKEEPING={'job_id','branch','parent_checkpoint','start_episode','episodes','mode',
             'rollout_terminal_episode','carry_complete_pending','rollout_protocol_path','rollout_protocol_sha256'}

def signature(config):
    return {k:v for k,v in config.items() if k not in BOOKKEEPING}

def resolve(rows, mapping, load_meta=None):
    load_meta=load_meta or (lambda p:json.loads(Path(p).with_suffix('.json').read_text()))
    assert all(k.startswith('RETENTION_') and v and not v.startswith('RETENTION_') for k,v in mapping.items()),'INVALID_LINEAGE_MAP'
    groups=defaultdict(list);errors=[];verified=[]
    for row in rows:
        branch=row['branch'];lineage=mapping.get(branch,branch)
        if branch.startswith('RETENTION_') and branch not in mapping:
            errors.append(dict(job=row['job_id'],error='UNREGISTERED_RETENTION_BRANCH'));continue
        if branch in mapping and row['mode']=='evaluation':
            try:
                path=row['parent'];seen=set();reference=None;found=False;chain=[]
                for _ in range(100):
                    assert path not in seen,'ANCESTRY_CYCLE'
                    seen.add(path);meta=load_meta(path)
                    assert isinstance(meta,dict),'INVALID_METADATA'
                    cfg=meta['research_config'];b=meta['branch']
                    assert isinstance(cfg,dict),'INVALID_TRAINING_CONFIG'
                    assert meta['seed']==row['seed'] and cfg['seed']==row['seed'],'SEED_CHANGED'
                    assert mapping.get(b,b)==lineage,'CROSS_METHOD_PARENT'
                    current=signature(cfg)
                    if reference is None:
                        reference=current
                        assert meta['continuation_episodes']==row['index']-1,'ENDPOINT_MISMATCH'
                        assert b==branch,'EVALUATED_CHECKPOINT_BRANCH_MISMATCH'
                    else:assert reference==current,'TRAINING_METHOD_CHANGED'
                    assert not meta.get('partial_attempt') and not meta.get('resume_requires_explicit_offline_pending_recovery'),'PARTIAL_PARENT'
                    chain.append(dict(checkpoint=path,branch=b,endpoint=meta['continuation_episodes']))
                    if b==lineage:found=True;break
                    path=meta['parent']
                assert found,'LINEAGE_ROOT_NOT_FOUND'
                verified.append(dict(job=row['job_id'],lineage=lineage,chain=chain))
            except (KeyError,AssertionError,ValueError,OSError,TypeError) as exc:
                errors.append(dict(job=row['job_id'],error=str(exc)));continue
        groups[lineage].append(row)
    return dict(groups=dict(groups),errors=errors,verified_ancestry=verified,
        status='PASS' if not errors else 'REVIEW_REQUIRED',branch_to_lineage=mapping)

def retained(groups,seeds):
    result=[]
    for name,rows in groups.items():
        mean=[x for x in rows if x['mode']=='evaluation' and x['policy_mode']=='deterministic']
        if mean and all(x['success'] for x in mean) and all(any(x['seed']==s and x['index']>=31 for x in mean) for s in seeds):result.append(name)
    return result

def latest_mean(comparisons,lineage,seed):
    candidates=[x for x in comparisons if x['lineage']==lineage and x['seed']==seed and x['mode']=='deterministic']
    return max(candidates,key=lambda x:x['continuation_endpoint']) if candidates else None


def longest_mean_evidence(groups,supported,seeds):
    mean={b:[x for x in xs if x['mode']=='evaluation' and x['policy_mode']=='deterministic'] for b,xs in groups.items()}
    horizon=max((x['index']-1 for xs in mean.values() for x in xs),default=0)
    tested={b for b,xs in mean.items() if all(any(x['seed']==s and x['index']-1==horizon for x in xs) for s in seeds)}
    at_horizon=[b for b in supported if b in tested]
    failures=[dict(lineage=b,job=x['job_id'],seed=x['seed'],endpoint=x['index']-1) for b,xs in mean.items() for x in xs if not x['success']]
    return dict(longest_tested_mean_endpoint=horizon,two_parent_families_tested_at_longest=sorted(tested),
                supported_at_longest_endpoint=at_horizon,all_tested_mean_failures=failures,
                interpretation='Untested longer horizons do not count as retained success. Earlier positive windows remain explicitly limited.')
