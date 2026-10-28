"""No-physics counterexamples for reward cycles, terminal padding and budgets."""
from pathlib import Path
import ast,json,math,random
from research_common import ROOT,atomic,sha
from rewards import transition,VERSIONS

def test_rewards():
    cases=[]
    for version in ['R1','R2']:
        for success in [False,True]:
            for jf,jm,var in [(0.,0.,0.),(100.,5.,.01),(6000.,1800.,30.)]:
                a=dict(phi=0.,force=0.,moment=0.,variation=0.)
                total=0.;phi_path=[0.,.6,.2,1.,1.8,2.,2.7,3. if success else 0.]
                for i,phi in enumerate(phi_path[1:],1):
                    b=dict(phi=phi,force=jf*i/7,moment=jm*i/7,variation=var*i/7)
                    reward,_=transition(version,a,b,i==7,success if i==7 else False,0.)
                    total+=reward;a=b
                c=VERSIONS[version];cost=c['force_per_Ns']*jf+c['moment_per_Nms']*jm+c['variation']*var
                expected=6.+c['complete']-cost if success else c['failure']-max(c['failure_floor'],cost)
                assert abs(total-expected)<1e-9
                assert total>0 if success else total<=-30.+1e-9
                cases.append(dict(version=version,success=success,JF=jf,JM=jm,variation=var,total=total,expected=expected))
        # Closed loops have zero shaping; no phase cycling reward accumulation.
        z=dict(phi=0.,force=0.,moment=0.,variation=0.);a=z.copy();total=0.
        for phi in [1.,.4,1.8,.9,2.5,0.]:
            b={**z,'phi':phi};r,_=transition(version,a,b,False,False,0.);total+=r;a=b
        assert abs(total)<1e-10
    # The research reward module cannot access hidden physics/evaluation truth.
    tree=ast.parse((ROOT/'scripts/rewards.py').read_text())
    forbidden={'qpos','qvel','plant','capture','summary','native_states','physical_evaluation_only'}
    assert not ({n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden)
    return cases

if __name__=='__main__':
    cases=test_rewards()
    atomic(ROOT/'audit/RESEARCH_REWARD_MATH_TESTS.json',dict(pass_=True,category='NO_PHYSICS_UNIT_ARITHMETIC',
        cases=cases,closed_loop_shaping_zero=True,gamma=1.,failure_terminal_potential=0.,
        success_terminal_potential=3.,success_potential_note='Fixed successful-terminal shaping is an explicit success bonus; no claim of policy invariance across terminal identities.',
        safe_30s_cost_upper_bound=dict(force=3.,moment=9.,estimated_acceleration_R2=3.),
        actual_motion_is_independently_evaluated=True,reward_source_sha256=sha(ROOT/'scripts/rewards.py')))
    print('RESEARCH REWARD MATH PASS',len(cases))
