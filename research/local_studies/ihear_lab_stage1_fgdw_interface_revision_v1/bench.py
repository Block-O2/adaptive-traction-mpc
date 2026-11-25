"""Sequential same-fixture timing in an isolated interpreter per backend."""
from fixture import HERE, fixture, read, seal
from matched import worker
import os
import platform
import sys
import numpy as np

def measure(name, backend=None):
    gate=read(HERE/'IAR_GATE.json')
    assert gate['decision']=='GO'
    c=fixture()
    rows=[]
    for k in range(6):
        packet,digest,size,ns,counts,paths,screen=worker(c,backend)
        assert digest==gate['packet_sha256'] and size==gate['size']
        assert len(paths)==35 and sum(x['mechanics']['sample_count'] for x in packet['checks'].values())==735
        rows.append(dict(index=k,mode='first' if k==0 else 'warm',ns=ns,objects=counts,
                         logical_samples=735,sha256=digest,kernel_counts=screen.counts if screen else {}))
    seal('timing_'+name+'.json',dict(rows=rows,units='ns',clock='perf_counter_ns',cpu=sorted(os.sched_getaffinity(0)),
         python=sys.version,numpy=np.__version__,kernel=platform.release(),threads={k:os.environ[k] for k in
             ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}))
    print(name,[round(row['ns']['worker_total']/1.e6,3) for row in rows])
