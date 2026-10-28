"""Read-only physical pre-fork history audit; no selection or refitting."""
from pathlib import Path
import json, hashlib, os, time
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1]
FIELDS=['estimated_human_state_rad_rad_s','evaluation_only_human_state_rad_rad_s',
        'reference_q_rad','reference_dq_rad_s','reference_ddq_rad_s2',
        'cr12_actuator_command_nm','physical_cuff_force_world_n',
        'physical_cuff_moment_world_nm','task_beta']
def fingerprint(root, group, ident_override=None, at_override=None):
    # COMPOSE follows the group's actual upstream policy; B can fork earlier.
    choices=[group+'_COMPOSE',group+'_RELATIVEP',group+'_B']
    ident=ident_override or next(n for n in choices if (root/'runtime/output'/(n+'_DATA.json')).exists())
    d=json.loads((root/'runtime/output'/(ident+'_DATA.json')).read_text())
    at=d['child']['physical_time_at_fork'] if at_override is None else at_override
    h=hashlib.sha256(); state=None; count=0
    with np.load(root/'runtime/source/results'/ident/'trace.npz') as z:
        task=z['stage']=='TASK'; use=task&(z['time_s']<at-1e-9)
        count=int(use.sum())
        for key in FIELDS:
            v=z[key]
            if len(v)==len(task):v=v[use]
            elif len(v)==int(task.sum()):v=v[z['time_s'][task]<at-1e-9]
            else:raise ValueError('UNALIGNED:'+group+':'+key)
            h.update(key.encode());h.update(np.round(v,10).tobytes())
        state=z['evaluation_only_human_state_rad_rad_s'][use][-1].tolist()
    return dict(group=group,representative=ident,physical_history_sha256=h.hexdigest(),
                last_pre_fork_q_dq=state,task_samples=count,fork_physical_s=at)
def main():
    model=json.loads((P/'models/COMMON_COMPOSE_FROZEN.json').read_text())
    train=[fingerprint(P,g) for g in model['train_groups']]
    tests=[fingerprint(P,g) for g in ['TEST_O1','TEST_O2','TEST_R1','TEST_R2']
           if (P/'data'/f'{g}.json').exists()]
    extras=[fingerprint(P,g) for g in ['LEGACY_NEW_O','LEGACY_BOUNDARY_O2','LEGACY_BOUNDARY_O3']
            if (P/'data'/f'{g}.json').exists()]
    aliases=[];risk_coverage=[]
    risk_sources=json.loads((P/'models/WHOLE_HISTORY_RISK_V5_FROZEN.json').read_text())['source_trajectories']
    for i,r in enumerate(tests+extras):
        same=[t['group'] for t in train+(tests+extras)[:i]
              if t['physical_history_sha256']==r['physical_history_sha256']]
        if same:aliases.append(dict(test=r['group'],same_actual_parent=same))
        r['nearest_training_current_q_dq_distance']=min(
            float(np.linalg.norm(np.array(r['last_pre_fork_q_dq'])-t['last_pre_fork_q_dq']))
            for t in train)
        # Risk training used many historical windows after their own earlier forks.
        # Compare complete pre-test histories at this actual test decision time,
        # rather than only historical cold-parent job names or their fork times.
        old_matches=[]
        for ident in risk_sources:
            q=fingerprint(P.parent/'smoothness_critic_research_v5',ident,
                          ident_override=ident,at_override=r['fork_physical_s'])
            if q['physical_history_sha256']==r['physical_history_sha256']:old_matches.append(ident)
        if old_matches:aliases.append(dict(test=r['group'],same_old_risk_training_history=old_matches))
        risk_coverage.append(dict(test=r['group'],old_risk_trajectories_checked=len(risk_sources),exact_history_matches=old_matches))
    reclassified=[];active_aliases=aliases.copy();independent_extras=extras.copy()
    classification=P/'audit/O3_PARENT_ALIAS_RECLASSIFICATION.json'
    if classification.exists():
        known=json.loads(classification.read_text())
        assert known['status']=='CONFIRMED_TRAINING_PARENT_REPLAY_RECLASSIFIED'
        reclassified=[r for r in extras if r['group']=='LEGACY_BOUNDARY_O3']
        independent_extras=[r for r in extras if r['group']!='LEGACY_BOUNDARY_O3']
        active_aliases=[r for r in aliases if r['test']!='LEGACY_BOUNDARY_O3']
    out=dict(status='PASS' if len(tests)==4 and not active_aliases else
             'IN_PROGRESS' if not active_aliases else 'FAIL_ACTUAL_PARENT_ALIAS',
             checked_unix=time.time(),audit_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),training=train,tests=tests,extra_frozen_risk_states=independent_extras,
             reclassified_training_parent_replays=reclassified,all_observed_aliases=aliases,unaccounted_claimed_independent_aliases=active_aliases,aliases=active_aliases,old_risk_training_coverage=risk_coverage,
             timing_and_group_names_excluded_from_fingerprint=True,
             rounding_units=1e-10,
             scope='Executed pre-fork observer/physical/reference/torque/belief history, '
             'candidate/future excluded. Same nominal Human, nearby legal prefixes; '
             'claimed independent histories must differ; O3 exact training-parent replay separately sealed and excluded. Distinct histories are not independent patients '
             'or a broad out-of-distribution generalization claim.')
    (P/'audit/FROZEN_TEST_ACTUAL_STATE_INDEPENDENCE.json').write_text(json.dumps(out,indent=2)+'\n')
    print('TEST_INDEPENDENCE',out['status'],'main',len(tests),'independent risk',len(independent_extras),'claimed aliases',active_aliases,'sealed replays',len(reclassified),flush=True)
    return out
if __name__=='__main__':main()
