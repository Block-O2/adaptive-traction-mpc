from extension_common import *

def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    timer=json.loads((EXT/'TIMER_SERVICE.json').read_text());keys=list(timer['groups']);g=timer['groups'];x=np.arange(len(keys));fig,axes=plt.subplots(2,1,figsize=(12.8,8.5),sharex=True)
    for ax,field,title in [(axes[0],'max_service_gap_ms','Largest main-loop service gap per saved-state job'),(axes[1],'elapsed_ms','Native job enqueue-to-collection time (idle is a timer-only control)')]:
        p50=[g[k][field]['p50'] for k in keys];p95=[g[k][field]['p95'] for k in keys]
        ax.bar(x-.17,p50,.34,label='p50');ax.bar(x+.17,p95,.34,label='p95');ax.set_ylabel('ms');ax.set_title(title);ax.grid(axis='y',alpha=.2);ax.legend(loc='upper left')
        for i,v in enumerate(p50):ax.text(i-.17,v+1,f'{v:.1f}',ha='center',fontsize=8)
    axes[0].axhline(5,color='black',linestyle='--',linewidth=1,label='5ms timer period')
    axes[1].set_xticks(x, [k.replace('process_duplicate','proc + parent work').replace('/','\n') for k in keys],fontsize=9)
    fig.suptitle('OFFLINE TIMER SERVICE — no physics, activation or qualification',fontsize=14)
    fig.text(.5,.025,'22 retained states × 4 sessions per condition; 88 timer-only controls + 704 timed native jobs.\nSame saved decision outputs within 1e-10; timer service excludes real feedback/plant/receipt cost. Nested duplicate work is retained.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.085,1,.955));folder=EXT/'figures';folder.mkdir(exist_ok=True);p=folder/'offline_timer_service.png';fig.savefig(p,dpi=160);plt.close(fig)
    save(EXT/'FIGURE_MANIFEST.json',dict(status='VISUAL_REVIEW_PENDING',figures=[dict(path=str(p),sha256=sha(p))],inputs={str(EXT/'TIMER_SERVICE.json'):sha(EXT/'TIMER_SERVICE.json')},scope='Offline timer only; no actual qualification claim.'))
    target=WIN_EXT/'preview';target.mkdir(exist_ok=True);shutil.copy2(p,target/p.name)
    print(json.dumps(dict(status='FIGURE_READY',path=str(target/p.name),sha256=sha(p))))

if __name__=='__main__':main()
