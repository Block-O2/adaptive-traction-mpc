"""Offline scientific memory figure; run only after bounded SAC exits."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/single_human_sac_memory/output')
def run():
    samples=json.loads((ROOT/'attempt5/MEMORY_SAMPLES.json').read_text())
    rows=[r for r in samples if r['step'] and r['step']>=15000]
    x=[r['step']/1000 for r in rows]
    fig,axes=plt.subplots(2,2,figsize=(12,7.2),sharex=True,constrained_layout=True)
    a=axes[0,0]
    a.plot(x,[r['processes']['owned'][0]['Rss']/2**30 for r in rows],label='Main RSS')
    a.plot(x,[r['processes']['owned'][0]['Pss']/2**30 for r in rows],label='Main PSS')
    a.plot(x,[sum(p.get('Pss',0) for p in r['processes']['owned'])/2**30 for r in rows],label='Tree PSS')
    peaks=json.loads((ROOT/'attempt5/EVALUATION_PEAK_SAMPLES.json').read_text())
    a.scatter([r['step']/1000 for r in peaks],[r['tree_pss_bytes']/2**30 for r in peaks],s=10,alpha=.45,label='OS observer tree PSS')
    a.set_ylabel('GiB');a.set_title('Process memory, including evaluation');a.legend(fontsize=8)
    a=axes[0,1]
    for k,label in [('MemAvailable','Available'),('Cached','Cached'),('SReclaimable','Reclaimable slab')]:a.plot(x,[r['wsl'][k]/2**30 for r in rows],label=label)
    a.plot(x,[r['swap_used_bytes']/2**30 for r in rows],label='Swap used');a.set_ylabel('GiB');a.set_title('WSL memory');a.legend(fontsize=8)
    a=axes[1,0]
    a.plot(x,[r['windows']['AvailableBytes']/2**30 for r in rows],label='Available')
    a.plot(x,[(r['windows']['CommitLimit']-r['windows']['CommittedBytes'])/2**30 for r in rows],label='Commit headroom')
    a.axhline(2,color='grey',ls=':',lw=1,label='Old Available stop / new commit reserve')
    a.set_ylabel('GiB');a.set_title('Windows host accounting');a.legend(fontsize=8)
    a=axes[1,1]
    a.plot(x,[r['torch_gpu']['allocated']/2**20 for r in rows],label='CUDA allocated')
    a.plot(x,[r['torch_gpu']['reserved']/2**20 for r in rows],label='CUDA reserved')
    a.plot(x,[r['replay']['allocated_array_bytes']/2**20 for r in rows],label='CPU replay capacity')
    a.plot(x,[r['replay']['used_payload_bytes']/2**20 for r in rows],label='CPU replay used payload')
    a.set_ylabel('MiB');a.set_title('GPU allocator and fixed replay capacity');a.legend(fontsize=8)
    for a in axes.flat:
        a.grid(alpha=.2);a.set_xlabel('Total SAC transitions (thousands)')
        for n in (15,20,25,30):a.axvline(n,color='grey',ls=':',lw=.6)
    fig.suptitle('SAC memory-only continuation: 15k / 20k / 25k / 30k, R2 unchanged',fontsize=13)
    fig.savefig(ROOT/'SAC_MEMORY_FIGURE_V1.png',dpi=170)
    print(ROOT/'SAC_MEMORY_FIGURE_V1.png')
if __name__=='__main__':run()
