"""Static scientific figures from preserved paired results; no inference."""
from task_bootstrap import *
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
 version=sys.argv[1] if len(sys.argv)>1 else 'v1'
 a=json.loads((STUDY/('ANALYSIS_'+version+'.json')).read_text());rows=a['rows'];pairs=a['paired'];methods=['M0','M1','M2','M3','M4'];groups=sorted({r['group'] for r in rows})
 fig,axs=plt.subplots(2,2,figsize=(11,7),layout='constrained');colors=['#555555','#1873ab','#c57913','#2b875b','#8a4b9a']
 for j,g in enumerate(groups):
  for i,m in enumerate(methods):
   rr=next((r for r in rows if r['method']==m and r['group']==g),None)
   if rr is None or rr.get('J_F') is None:continue
   mark='o' if rr['valid'] else 'x';x=i+(j-(len(groups)-1)/2)*.07
   axs[0,0].plot(x,rr['J_F'],mark,color=colors[i],ms=6,alpha=.8)
   if rr['valid']:axs[0,1].plot(x,rr['moment_integral'],mark,color=colors[i],ms=6,alpha=.8)
   if rr.get('coordinator_max_s') is not None:axs[1,1].plot(x,1000*rr['coordinator_max_s'],mark,color=colors[i],ms=6,alpha=.8)
 for i,m in enumerate(methods[1:],1):
  pp=[p for p in pairs if p['method']==m and p['valid_comparable']]
  for j,p in enumerate(pp):axs[1,0].plot(i+(j-(len(pp)-1)/2)*.07,p['J_F_improvement_pct'],'o',color=colors[i],ms=6)
 for ax in axs.flat:ax.set_xticks(range(5),methods);ax.grid(axis='y',alpha=.2)
 axs[0,0].set_ylabel('Full task J_F (N s)');axs[0,0].set_title('Each paired run; x = invalid, unranked')
 axs[0,1].set_ylabel('Moment integral (N m s)');axs[0,1].set_title('Complete VALID tasks only')
 axs[1,0].set_ylabel('Paired J_F improvement over B (%)');axs[1,0].axhline(0,color='gray',lw=.8);axs[1,0].set_title('One exposed Human; no significance claim')
 axs[1,1].set_ylabel('Maximum coordinator latency (ms)');axs[1,1].axhline(40,color='red',lw=.8,ls='--',label='entire B handoff bridge (40 ms)');axs[1,1].legend(fontsize=8);axs[1,1].set_title('Coordinator is only part of end-to-end activation')
 fig.suptitle('B-native learning matrix '+version+' — scientific simulation',fontsize=14)
 folder=STUDY/'reports';folder.mkdir(exist_ok=True)
 for ext in ('png','pdf'):fig.savefig(folder/('matrix_'+version+'.'+ext),dpi=180)
 plt.close(fig);print('FIGURES_SAVED',version)
if __name__=='__main__':main()
