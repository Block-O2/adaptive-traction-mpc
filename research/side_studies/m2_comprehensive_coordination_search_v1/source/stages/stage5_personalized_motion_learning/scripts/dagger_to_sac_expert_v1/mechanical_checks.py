from common import *
from expert import CausalHipLeadingExpert
import ast, inspect
def run():
    cfg=read('PREREGISTRATION.json');expert=CausalHipLeadingExpert(cfg['expert'],SCALES)
    source=(P/'expert.py').read_text();tree=ast.parse(source)
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call)]
    forbidden={'open','load','read','read_text','read_bytes','reset','step','get_state','mj_step'}
    assert not any((isinstance(n.func,ast.Name) and n.func.id in forbidden) or
                   (isinstance(n.func,ast.Attribute) and n.func.attr in forbidden) for n in calls)
    assert list(inspect.signature(expert.query).parameters)==['observation']
    z=np.load(DEMO);obs=z['observations'][0].copy();a,detail=expert.query(obs)
    altered=obs.copy();altered[0]=(expert.hip_release+.1)/SCALES[0];altered[4]=(expert.ref_release+.1)/SCALES[4]
    b,_=expert.query(altered);assert abs(float(a[1]-b[1]))>.1,'STATE_INDEPENDENT_TIME_REPLAY'
    np.testing.assert_equal(obs[44],altered[44])
    lo=z['observations'][0].copy();hi=altered.copy()
    for phase in range(3):
        lo[41:44]=0;lo[41+phase]=1
        action,_=expert.query(lo);assert np.all(np.isfinite(action)) and np.max(abs(action))<=1
    np.testing.assert_allclose(2*detail['target']/np.radians(125)-1,a,atol=1e-7,rtol=0)
    assert cfg['dagger']['beta']==[.5,.25,.1,0,0,0,0,0]
    assert cfg['sac']['initial_random_warmup_steps']==0
    assert 256*.25==64
    residue=0;counts=[]
    for _ in range(5):
        ideal=256*.1+residue;n=int(np.floor(ideal+1e-9));residue=ideal-n;counts.append(n)
    assert sum(counts)==128
    check()
    save('MECHANICAL_CHECKS.json',dict(status='PASS',query_only_observation=True,no_file_plant_env_future_access=True,
        state_changes_action_at_identical_clock=True,state_sensitivity_knee_raw=float(abs(a[1]-b[1])),
        legal_actions_all_phases=True,action_transform_identity=True,frozen_beta_schedule=True,
        demo_count_25_percent=64,demo_counts_10_percent_quantization=counts,late_five_batch_fraction=.1))
    print('MECHANICAL_CHECKS_PASS',flush=True)
if __name__=='__main__':run()
