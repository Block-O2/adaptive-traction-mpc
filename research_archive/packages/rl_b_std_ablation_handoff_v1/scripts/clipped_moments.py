"""Exact clipped Gaussian moments at identical initial observations, no simulation."""
from pathlib import Path
import math,json
from research_common import ROOT,read,atomic,now,sha
from scipy.integrate import quad

def moments(mu,sigma):
 a=(-1-mu)/sigma;b=(1-mu)/sigma
 Phi=lambda x:.5*(1+math.erf(x/math.sqrt(2)))
 phi=lambda x:math.exp(-x*x/2)/math.sqrt(2*math.pi)
 lo=Phi(a);hi=1-Phi(b);p=Phi(b)-Phi(a)
 mean=-lo+mu*p+sigma*(phi(a)-phi(b))+hi
 second=lo+(mu*mu+sigma*sigma)*p+2*mu*sigma*(phi(a)-phi(b))+sigma*sigma*(a*phi(a)-b*phi(b))+hi
 pdf=lambda x:math.exp(-.5*((x-mu)/sigma)**2)/(sigma*math.sqrt(2*math.pi))
 numeric_mean=-lo+quad(lambda x:x*pdf(x),-1,1,epsabs=1e-12)[0]+hi
 numeric_second=lo+quad(lambda x:x*x*pdf(x),-1,1,epsabs=1e-12)[0]+hi
 assert abs(mean-numeric_mean)<1e-10 and abs(second-numeric_second)<1e-10
 return dict(mean=mean,std=math.sqrt(max(0,second-mean*mean)),clip_lower_probability=lo,clip_upper_probability=hi,clip_probability=lo+hi,quadrature_check=True)

def main():
 cases=[]
 for seed in [1495656323,1630784693]:
  run=ROOT/f'runtime/jobs/identity_seed{seed}_C_202610213100/episode_061';t=read(run/'RESEARCH_TRANSITIONS.json')[0];mu=t['mean'];std=t['std'];a=[moments(x,y) for x,y in zip(mu,std)];b=[moments(x,.20000000298023224) for x in mu]
  cases.append(dict(seed=seed,network_mean=mu,checkpoint_std=std,A_clipped_gaussian=a,B_clipped_gaussian=b,C_clipped_mean=[max(-1,min(1,x)) for x in mu],source_sha256=sha(run/'RESEARCH_TRANSITIONS.json')))
 atomic(ROOT/'audit/CLIPPED_GAUSSIAN_MOMENTS.json',dict(time_utc=now(),cases=cases,numerical_quadrature_all_pass=True,new_physics=0,Adam=0,scope='Exact distribution of bounded proposals at a shared initial observation; not planner-accepted actions or applied torque expectation',interpretation='Changing pre-clip STD changes both variance and expected bounded proposal. Actor mean/weights remain fixed. This is an evaluation distribution intervention, not a pure variance-only intervention after clipping.'))
 print(json.dumps(cases))
if __name__=='__main__':main()
