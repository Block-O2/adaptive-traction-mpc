"""Focused software invariants; no physics and no formal updates."""
from common import *
def run():
    case,options=load_case_options();env=SACExpertEnv(O/'harness_unused',case,options,.02,'NATIVE',False)
    z=np.load(O/'NATIVE_DEMO.npz');b=PairedReplay(6000,env.observation_space,env.action_space,device='cuda',handle_timeout_termination=False,demo_path=O/'NATIVE_DEMO.npz')
    a=PairedReplay(6000,env.observation_space,env.action_space,device='cuda',handle_timeout_termination=False)
    original=ReplayBuffer(6000,env.observation_space,env.action_space,device='cuda',handle_timeout_termination=False)
    for i in range(5001):
        k=i%593
        args=(z['observations'][k:k+1],z['next_observations'][k:k+1],z['actions'][k:k+1],z['rewards'][k:k+1],np.array([bool(z['terminated'][k] or z['truncated'][k])]),[{}])
        for buf in (a,b,original):buf.add(*args)
    initial=rng();ab=a.sample(256);restore(initial);ob=original.sample(256)
    assert all(torch.equal(x,y) for x,y in zip(ab,ob))
    for _ in range(20):bb=b.sample(256);assert bb.observations.shape==(256,55)
    assert b.demo_sample_counts.sum()==b.online_sample_counts.sum()==2560
    recovered=pickle.loads(pickle.dumps(b));assert not recovered.demo.observations.flags.writeable
    try:recovered.demo.add(*args);raise AssertionError('Demo add allowed')
    except RuntimeError:pass
    assert recovered.sampler_rng.bit_generator.state==b.sampler_rng.bit_generator.state
    x=b.sample(256);y=recovered.sample(256)
    assert all(torch.equal(xv[:128],yv[:128]) for xv,yv in zip(x,y))
    small=PairedReplay(2,env.observation_space,env.action_space,device='cuda',handle_timeout_termination=False,demo_path=O/'NATIVE_DEMO.npz')
    dh=hashlib.sha256(small.demo.observations.tobytes()).hexdigest()
    for i in range(10):small.add(*args)
    assert small.size()==2 and dh==hashlib.sha256(small.demo.observations.tobytes()).hexdigest()
    small.online_steps=5000
    try:small.sample(256);raise AssertionError('Demo triggers early learning')
    except AssertionError as ex:assert 'online count' in str(ex)
    save('HARNESS_VALIDATION.json',dict(status='PASS',A_sampling_identical_to_SB3=True,fixed_B_batch_128_128=True,immutable_roundtrip=True,sampler_rng_roundtrip=True,online_wrap_cannot_overwrite_demo=True,learning_starts_not_triggered_by_demo=True,formal_steps=0,formal_updates=0))
    env.close();print('HARNESS_VALIDATION_PASS',flush=True)
if __name__=='__main__':run()
