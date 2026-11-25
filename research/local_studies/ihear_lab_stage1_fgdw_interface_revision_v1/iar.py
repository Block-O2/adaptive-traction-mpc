"""Independent fixture comparison and Level 1 stage gate, prior to any benchmarking."""
from fixture import HERE,PREV,old,read,seal,fixture,sha
from matched import worker
import numpy as np

def main():
    c=fixture()
    baseline=old.main()
    prior=read(PREV/'ia.json')
    packet,digest,size,_,_,paths,_=worker(c)
    assert baseline['base_positive']['feasible'] and baseline['base_matches_archive']
    assert packet['identity']==prior['identity'] and packet['source_capture_ns']==prior['metadata']['source_capture_ns']
    assert np.array_equal(packet['target'],baseline['r']) and np.array_equal(packet['end'],prior['end'])
    assert np.array_equal(packet['scores'],[x['score_N'] for x in baseline['raw_directions']])
    assert np.array_equal(packet['offset'],prior['current']['offset'])
    original={'normal':prior['normal']}
    for i,st in enumerate(prior['stops']):
        name='stop'+str(i);original[name]=st['whole']
        original.update({name+'/'+k:v for k,v in st['pieces'].items()})
    native_cross=[]
    for name,path in paths:
        proof=packet['checks'][name]
        for key in ('nominal','shifted','mechanics'):assert proof[key]==original[name][key],(name,key)
        # Compare against native geometry on the service grid in addition to the continuous certificate.
        ticks=round(path.duration_s/.005)
        qs=np.array([path.sample(t).q_rad for t in np.linspace(0.,path.duration_s,ticks+1)])
        for scope,off in [('nominal',0.),('shifted',np.asarray(packet['offset']))]:
            shifted=qs+off
            margins=c.clear.envelope.margins(shifted)
            existing=np.asarray(c.clear.shank_contract.evaluate(shifted))
            np.testing.assert_allclose(margins['distal_shank_m'],existing,rtol=0,atol=1e-15)
            lower=proof[scope]['floor_m']
            assert np.all(c.clear.evaluate(shifted)>=lower)
            native_cross.append(dict(name=name,scope=scope,samples=len(qs),minima={k:min(v) for k,v in margins.items()}))
    for new,prev in zip(packet['planes'],prior['plane']):
        assert all(np.array_equal(new[k],prev[k]) for k in ('human','cuff','tcp'))
    assert [z['brake_s'] for z in packet['stops']]==[z['brake_s'] for z in prior['stops']]
    gate=read(PREV/'GATE.json')
    assert gate['decision']=='LIMITED' and gate['scopes']['search_box_shifted']['UNRESOLVED']==35
    seal('iar_packet.json',packet)
    seal('IAR_GATE.json',dict(stage='I-A-R',decision='GO',scope='startup offline prepared Level 1 only',level2='UNRESOLVED / FUTURE_RESEARCH',
        base=baseline['base_positive'],prior_packet_match=True,packet_sha256=digest,size=size,
        original_clearance_contract=c.registered,rom=c.rom,V=c.V,A=c.A,phase_limit=c.phase_limit,task_limit=c.task_limit,
        sampled_native_crosscheck=native_cross,count=len(paths),native_writes=0,physics_steps=0))
    print('I-A-R GO',digest,len(paths),max(max(item['junctions']) for item in packet['stops']))
if __name__=='__main__':main()
