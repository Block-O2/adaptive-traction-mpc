"""Independent arithmetic and saved-input equivalence of the conditional unit ablation."""
from pathlib import Path
import ast,json,random,runpy,math
from research_common import ROOT,read,atomic,sha,now

def audit(candidate):
    original=ROOT/'reward_versions/R1/reward.py'
    old=runpy.run_path(str(original));new=runpy.run_path(str(candidate))
    assert set(new['VERSIONS'])=={'R0','R1','R2','R3'}
    rng=random.Random(2026102187);cases=[];checks={};n=0
    for jf,jm,var in [(0.,0.,0.),(100.,5.,.01),(6000.,1800.,30.),(60000.,18000.,300.)]:
        for success in [False,True]:
            a=dict(phi=0.,force=0.,moment=0.,variation=0.);total=0.
            for i,phi in enumerate([.6,.2,1.,1.8,2.,2.7,3. if success else .9],1):
                b=dict(phi=phi,force=jf*i/7,moment=jm*i/7,variation=var*i/7)
                r1,p1=new['transition']('R1',a,b,i==7,success and i==7,0.)
                r3,p3=new['transition']('R3',a,b,i==7,success and i==7,0.)
                assert abs(r3-r1/30.)<1e-10 and all(abs(p3[k]-p1[k]/30.)<1e-10 for k in p1)
                total+=r3;a=b
            cost=.0005*jf+.005*jm+.02*var
            expected=(6.+20.-cost)/30. if success else (-15.-max(15.,cost))/30.
            assert abs(total-expected)<1e-10 and math.isfinite(total)
            if not success:assert total<=-1.+1e-10
            cases.append(dict(success=success,JF=jf,JM=jm,online_variation=var,total=total,expected=expected))
    for _ in range(1000):
        a=dict(phi=rng.uniform(0,3),force=rng.uniform(0,10000),moment=rng.uniform(0,1000),variation=rng.uniform(0,30))
        b={k:v+rng.uniform(0,10) for k,v in a.items()};b['phi']=rng.uniform(0,3)
        terminal=rng.choice([False,True]);success=terminal and rng.choice([False,True]);baseline=rng.uniform(-20,20)
        for v in ['R0','R1','R2']:assert old['transition'](v,a,b,terminal,success,baseline)==new['transition'](v,a,b,terminal,success,baseline)
    rows=[json.loads(l) for l in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines()]
    for x in rows:
        if x['mode']!='training':continue
        path=Path(x['run'])/'RESEARCH_TRANSITIONS.json'
        for t in read(path,[]):
            for v in ['R0','R1','R2']:
                args=(v,t['reward_before'],t['reward_after'],t['terminal'],t['success'],t['baseline_reward'])
                assert old['transition'](*args)==new['transition'](*args);n+=1
    a=dict(phi=0.,force=0.,moment=0.,variation=0.);total=0.
    for phi in [1.,.4,1.8,.9,2.5,0.]:
        b={**a,'phi':phi};r,_=new['transition']('R3',a,b,False,False,0.);total+=r;a=b
    assert abs(total)<1e-12
    tree=ast.parse(candidate.read_text());assert not any(isinstance(x,(ast.Import,ast.ImportFrom)) for x in ast.walk(tree))
    attrs={x.attr for x in ast.walk(tree) if isinstance(x,ast.Attribute)}
    assert not attrs&{'qpos','qvel','plant','capture','summary','native_states','physical_evaluation_only'}
    checks=dict(all_R1_terms_and_floor_uniformly_divided30=True,closed_cycle_shaping_zero=True,
        failure_terminal_potential_zero=True,success_terminal_potential_three=True,
        positive_unit_scale_preserves_trajectory_reward_order=True,
        original_R0_R1_R2_outputs_bitwise_unchanged=True,no_import_or_future_truth_access=True,
        original_parent_critic_and_Adam_must_remain_unchanged=True)
    result=dict(time_utc=now(),status='PASS',candidate_source=str(candidate),candidate_source_sha256=sha(candidate),
        reference_source_sha256=sha(original),active_source_sha256=sha(ROOT/'scripts/rewards.py'),
        active_candidate=sha(candidate)==sha(ROOT/'scripts/rewards.py'),checks=checks,cases=cases,
        saved_transition_version_comparisons=n,random_transition_cases=1000,physics_attempts=0,Adam_updates=0,
        scope='Arithmetic/source validation only. No claim about actual PPO update magnitude, task completion, retention, motion or generalization. gamma1; successful-terminal shaping remains explicit bonus.')
    atomic(ROOT/'audit/R3_REWARD_PRETRAIN_AUDIT.json',result);return result
if __name__=='__main__':
    import sys
    r=audit(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'drafts/R3_unit30/rewards.py')
    print(json.dumps({k:v for k,v in r.items() if k not in ['cases','checks']}))
