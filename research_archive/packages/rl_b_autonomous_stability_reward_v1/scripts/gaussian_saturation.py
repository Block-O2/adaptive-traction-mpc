"""Exact Gaussian clipping integrals on saved causal observations; no physics.

These are pre-admission proposal statistics, never actual applied torque. Changed
exploration also changes future occupancy, so no task outcome is predicted here.
"""
from pathlib import Path
import sys,json,math
from research_common import ROOT,RUNTIME,atomic,sha,now
sys.path.insert(0,str(RUNTIME))
import common
import numpy as np,torch
from stable_baselines3 import PPO
torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.set_grad_enabled(False)
HISTORY=ROOT.parent/'rl_b_autonomous_replication_v1'

def integrate(mu,std):
    mu=np.asarray(mu,dtype=float);std=np.broadcast_to(np.asarray(std,dtype=float),mu.shape)
    alpha=(-1-mu)/std;beta=(1-mu)/std
    cdf=np.vectorize(lambda x:.5*(1+math.erf(float(x)/math.sqrt(2))))
    phi=lambda x:np.exp(-x*x/2)/math.sqrt(2*math.pi)
    a=cdf(alpha);b=cdf(beta)
    mass=a+1-b
    expected=mu*(b-a)+std*(phi(alpha)-phi(beta))+1-b-a
    return mass,expected
def main():
    evaluations=[json.loads(x) for x in (HISTORY/'ALL_EVALUATION_LOG.jsonl').read_text().splitlines()]
    output=[]
    for seed in [1495656323,1630784693]:
        e=next(x for x in evaluations if x['training_seed']==seed and x['kind']=='checkpoint050_first')
        p=HISTORY/e['run'];z=next(p.glob('transitions_*.npz'));obs=np.load(z)['obs']
        cp=HISTORY/f'seeds/{seed}/stage1/checkpoints/episode_050.zip'
        model=PPO.load(cp,device='cpu');model.policy.set_training_mode(False)
        with torch.no_grad():d=model.policy.get_distribution(torch.tensor(obs));mu=d.distribution.mean.numpy();sd=d.distribution.stddev.numpy()
        deterministic=np.clip(mu,-1,1)
        cases=[]
        for label,sigma in [('original_learned_std',sd),('counterfactual_std0.2',.2),('counterfactual_std0.1',.1)]:
            mass,expected=integrate(mu,sigma)
            ss=np.broadcast_to(np.asarray(sigma),mu.shape)
            cases.append(dict(label=label,expected_clipped_component_fraction=float(mass.mean()),
                expected_clipped_fraction_per_component=mass.mean(0).tolist(),
                initial_clipped_fraction=mass[0].tolist(),initial_clipped_Gaussian_proposal_mean=expected[0].tolist(),
                initial_deterministic_clipped_mean=deterministic[0].tolist(),
                proposal_mean_absolute_gap_to_deterministic=np.mean(np.abs(expected-deterministic),axis=0).tolist(),
                maximum_proposal_mean_gap=float(np.max(np.abs(expected-deterministic))),
                unbounded_proposal_increment_std_deg=(ss.mean(0)*np.asarray([11.5,11.])).tolist()))
        output.append(dict(seed=seed,checkpoint=str(cp),checkpoint_sha256=sha(cp),
             legal_observation_source=str(z),observation_sha256=sha(z),observations=len(obs),
             parent_mean_min=mu.min(0).tolist(),parent_mean_max=mu.max(0).tolist(),cases=cases))
    # Deterministic arithmetic checks independent of any loaded robot policy.
    mass,expect=integrate([[0.,0.]],1.)
    assert np.max(np.abs(expect))<1e-12
    assert abs(float(mass[0,0])-(1-math.erf(1/math.sqrt(2))))<1e-12
    _,narrow=integrate([[.4,-.4]],.001)
    assert np.max(np.abs(narrow-np.asarray([[.4,-.4]])))<1e-12
    atomic(ROOT/'audit/GAUSSIAN_CLIP_PROPOSAL_DIAGNOSIS.json',dict(time_utc=now(),source_sha256=sha(Path(__file__)),
         category='EXACT_SAVED_POLICY_PROPOSAL_INTEGRALS_NO_PHYSICS_NO_ADAM',cases=output,arithmetic_checks_pass=True,
         semantics='E[clip(Gaussian sample)] versus clip(policy mean), before planner/admission and applied torque',
         physical_scale='Original unbounded waypoint proposal fraction maps raw action change to .1*registered span; remaining-distance and original safety/certificate still apply.',
         limitations='Only original050 observed deterministic trajectories. Counterfactual std calculations are not trained/evaluated policies, independent initial states, or task-success predictions. Raw Gaussian likelihood remains the original PPO latent-action contract.'))
    print('Gaussian clipping diagnosis saved; policies',len(output),'new physics/Adam0')
if __name__=='__main__':main()
