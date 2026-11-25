"""Independent numerical trace comparison and offline current-input timing. Never activates."""
from collections import Counter
from time import perf_counter_ns
import numpy as np
from fixture import (HERE,ia,old,fixture,read,seal,sha,current_state,continuous_geometry,mechanics)
from matched import worker
from reuse import Screen


def profile(c, expected):
    output={}
    for kind,reuse in [('original',False),('exact',True)]:
        packet,digest,_,_,_,_,screen=worker(c,lambda c:Screen(c,reuse=reuse,audit=True))
        assert digest==expected
        m=screen.m
        output[kind]=dict(kernel_ns=m.ns,counts=m.counts,ordered_row_digests={k:h.hexdigest() for k,h in m.traces.items()})
        for name in ('sample','inverse_dynamics','allocate_generalized_action','state_residual_nm'):
            assert m.counts[name+'_executed']+m.counts[name+'_hit']==735
    assert output['original']['ordered_row_digests']==output['exact']['ordered_row_digests']
    return output


def latest(c,packet,normal):
    # Exercise dependency predicates on the archived observation, with no application authority.
    first=normal.sample(0)
    offset=current_state(c,first)
    if not (packet['model']==sha(repr(ia.model_key(c.b,c.clear)).encode()) and
            packet['geometry']==old.clearance_geometry_signature(c.clear) and
            packet['phase']==c.phase.value and packet['identity']==normal.identity and
            packet['owner']==normal.origin.owner and packet['source_time']==c.stamp and
            packet['source_capture_ns']==c.capture and c.elapsed==packet['elapsed'] and
            max(s['reserve_s'] for s in packet['stops'])<=min(c.phase_limit,c.task_limit)-c.elapsed and
            np.array_equal(ia.vec(first),np.r_[c.q,0.,0.,0.,0.]) and
            offset.tobytes()==packet['offset'].tobytes()):
        raise ValueError('prepared binding mismatch')
    return offset


def replay(c,packet,paths):
    out=[]
    for i in range(6):
        t=perf_counter_ns()
        off=latest(c,packet,paths[0][1])
        matched=perf_counter_ns()-t
        geo=Counter(); direct=Counter()
        for name,path in paths:
            start=perf_counter_ns()
            proof=continuous_geometry(path,c.clear.envelope,off,0.,c.rom)
            geo[name]=perf_counter_ns()-start
            assert proof==packet['checks'][name]['shifted']
        # Isolate the existing synchronous native model screen on the selected normal reference.
        normal=paths[0][1]
        endpoint=normal.sample(normal.duration)
        candidate=old.runtime._candidate('fgdw_interface_fixture',c.phase,endpoint.q_rad,endpoint.dq_rad_s,c.spec)
        start=perf_counter_ns()
        native=mechanics(c.b,candidate,normal)
        direct['normal_native_screen']=perf_counter_ns()-start
        assert native==packet['checks']['normal']['mechanics']
        out.append(dict(exact_binding_ns=matched,shifted_ns=dict(geo),native_ns=dict(direct)))
    return out


def main():
    c=fixture()
    gate=read(HERE/'IAR_GATE.json')
    for name in ('original','exact'):
        assert len(read(HERE/('timing_'+name+'.json'))['rows'])==6
    result=profile(c,gate['packet_sha256'])
    packet,digest,_,_,_,paths,_=worker(c)
    result['current_replay']=replay(c,packet,paths)
    result['packet']=digest
    seal('diagnostics.json',result)
    print('row-level identity',result['original']['ordered_row_digests'])
    print('true kernel ms', {k: {n: round(t/1e6,2) for n,t in v['kernel_ns'].items()} for k,v in result.items() if k in ('original','exact')})
if __name__=='__main__':main()
