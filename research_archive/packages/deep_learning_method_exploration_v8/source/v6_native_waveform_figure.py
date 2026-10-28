"""Standalone native plots; displayed decimation never replaces raw scoring."""
from pathlib import Path
import os,json,sys,hashlib,time
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLCONFIGDIR=str(P/'runtime/tmp/mpl'))
import numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
sys.path[:0]=[str(P/'runtime/code'),str(P/'runtime/deps')]
from stream_runtime_evidence import array_items
D=P/'figures';D.mkdir(exist_ok=True)
def sha(q):return hashlib.sha256(q.read_bytes()).hexdigest()
def main():
    group='RULE_T1' if (P/'data/RULE_T1.json').exists() else 'PHASE_RULE_S1' if (P/'data/PHASE_RULE_S1.json').exists() else 'DEV_O1'
    available={r['tag']:r for r in json.loads((P/'data'/f'{group}.json').read_text()) if r['horizon_s']==.5}
    cfg=json.loads((P/'experiments'/f'{group}.json').read_text())
    if cfg.get('matched_reference_group'):
        reference={r['tag']:r for r in json.loads((P/'data'/f"{cfg['matched_reference_group']}.json").read_text()) if r['horizon_s']==.5}
        available=dict(reference,**available)
    tags=[t for t in ['BEST','COMPOSE','BLEND','RULE']+(['HANDOFF'] if group.startswith('PHASE_RULE') else []) if t in available];provenance=[]
    fig,axs=plt.subplots(3,1,figsize=(11,8),sharex=True)
    colors=dict(BEST='#777777',COMPOSE='#2171b5',BLEND='#e6550d',RULE='#238b45',HANDOFF='#238b45')
    for tag in tags:
        ident=available[tag]['id'];cache=P/'analysis'/f'{ident}_NATIVE_PLOT_SERIES.npz'
        raw=P/'runtime/source/results'/ident/'runtime_artifacts.json.gz'
        with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
            times=z['time_s'][z['stage']=='TASK'];lo,hi=float(times[0]),float(times[-1])
        if not cache.exists():
            t=[];w=[]
            for r in array_items(raw,'native_states_evaluation_only'):
                if lo-1e-9<=r['time_s']<=hi+1e-9:
                    t.append(r['time_s']);w.append(r['cuff_wrench_world_evaluation_only'])
            with np.load(P/'runtime/motion_series'/f'{ident}.npz') as z:
                mt=z['time_s'];j=np.rad2deg(z['jerk_rad_s3'])
            assert np.max(abs(np.array(t)-mt))<1e-9
            np.savez_compressed(cache,time_s=np.array(t)-lo,wrench=np.array(w),jerk_deg_s3=j)
        with np.load(cache) as z:
            t=z['time_s'];w=z['wrench'];j=z['jerk_deg_s3'];rate=np.gradient(np.linalg.norm(w[:,:3],axis=1),t,edge_order=2)
            stride=20
            label='Fixed phase rule' if tag=='HANDOFF' else tag
            if not available[tag]['qualified']:label+=' (motion FAIL)'
            axs[0].plot(t[::stride],j[::stride,0],label=label,lw=.8,color=colors[tag],alpha=.85)
            axs[1].plot(t[::stride],np.linalg.norm(w[::stride,:3],axis=1),lw=1.,color=colors[tag])
            axs[2].plot(t[::stride],rate[::stride],lw=.8,color=colors[tag])
        provenance.append(dict(id=ident,raw_sha256=sha(raw),cache_sha256=sha(cache),native_samples=len(t),
            original_qualified=available[tag]['qualified'],metrics=available[tag]['metrics']))
    axs[0].set_ylabel('Native hip jerk (deg/s$^3$)');axs[1].set_ylabel('Cuff force magnitude (N)')
    axs[2].set_ylabel('Force magnitude rate (N/s)');axs[2].set_xlabel('TASK elapsed (s)')
    axs[0].legend(frameon=False,ncol=len(tags))
    for ax in axs:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    fig.suptitle(group+': actual native trajectories; original qualification gates')
    fig.text(.10,.015,'Display: every 20th native sample (5 ms); reported RMS uses every unfiltered 0.25 ms sample.\nJF/JM retain the original 5 ms left integral. Lower jerk/rate does not establish patient comfort.',fontsize=9)
    fig.tight_layout(rect=(0,.06,1,.96))
    for ext in ['png','pdf']:fig.savefig(D/('04_NATIVE_WAVEFORMS.'+ext),dpi=180,bbox_inches='tight')
    plt.close(fig)
    (P/'audit/NATIVE_WAVEFORM_FIGURE_PROVENANCE.json').write_text(json.dumps(dict(group=group,generated_unix=time.time(),
        displayed_stride=20,native_dt_s=.00025,raw_evaluation_unchanged=True,rows=provenance),indent=2)+'\n')
    print('NATIVE_WAVEFORMS',group,tags,flush=True)
if __name__=='__main__':main()
