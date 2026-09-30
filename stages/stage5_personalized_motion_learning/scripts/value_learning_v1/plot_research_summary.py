"""Standalone scientific figures from measured research evidence only."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from research_campaign import D,sha,save

def finish(fig,name):
 fig.savefig(D/(name+'.png'),dpi=180,bbox_inches='tight')
 fig.savefig(D/(name+'.svg'),bbox_inches='tight');plt.close(fig)

def main():
 matched=json.loads((D/'BEST_KNOWN_REFERENCE_TABLE.json').read_text())
 native=json.loads((D/'NATIVE_BEST_KNOWN_REFERENCE_TABLE.json').read_text())
 curve=json.loads((D/'ALL_REFERENCE_SEARCH_CONVERGENCE.json').read_text())
 fig,axes=plt.subplots(3,2,figsize=(11,10),layout='constrained')
 colors={'MATCHED_CONDITIONAL':'#2563eb','NATIVE_PRIMARY':'#d97706'}
 for ax,m,n in zip(axes.flat,matched['rows'],native['rows']):
  for scope,row,label in [('MATCHED_CONDITIONAL',m,'Matched conditional'),('NATIVE_PRIMARY',n,'Native primary objective')]:
   points=[p for p in curve if p['condition']==m['condition'] and p['scope']==scope]
   x=[0]+[p.get('evaluation_count',p.get('evaluation')) for p in points]
   y=[0.]+[row['previous_best_J_F_n_s']-p['best_known_J_F_n_s'] for p in points]
   ax.step(x,y,where='post',color=colors[scope],label=label)
  ax.set_title(m['condition']);ax.set_xlabel('Completed real evaluations');ax.set_ylabel('Improvement over prior reference (N s)')
  ax.axhline(0,color='#9ca3af',lw=.8);ax.grid(alpha=.2)
 axes.flat[0].legend(fontsize=9);fig.suptitle('Finite-budget best-known search; no global-optimality claim')
 finish(fig,'REFERENCE_SEARCH_FIGURE')
 fig,axes=plt.subplots(3,2,figsize=(11,10),layout='constrained')
 for ax,m,n in zip(axes.flat,matched['rows'],native['rows']):
  for row,color,label in [(m,'#2563eb','Matched conditional'),(n,'#d97706','Native primary')]:
   gains=[row['previous_best_J_F_n_s']-row['best_vs_level'][str(l)] for l in (0,1,2,3)]
   ax.plot([0,2,5,7],gains,'o-',color=color,label=label)
   for level,dof,gain in zip((1,2,3),(2,5,7),gains[1:]):
    count=row['level_evaluations'][str(level)]
    ax.annotate(f'n={count}',(dof,gain),textcoords='offset points',xytext=(0,5 if color=='#2563eb' else -14),ha='center',fontsize=8,color=color)
  ax.set_title(m['condition']);ax.set_xticks([0,2,5,7]);ax.set_xlabel('Nominal path coefficient count');ax.set_ylabel('Cumulative best improvement (N s)');ax.grid(alpha=.2)
 axes.flat[0].legend(fontsize=9);fig.suptitle('Nested best envelope; sparse or zero coverage does not establish a plateau')
 finish(fig,'PATH_FREEDOM_FIGURE')
 fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
 for ax,filename,title in zip(axes,('KNOWN_BENEFIT_CAPTURE.json','PRIMARY_OBJECTIVE_KNOWN_BENEFIT_CAPTURE.json'),('Matched conditional capture','Absolute native-objective capture')):
  rows=json.loads((D/filename).read_text())['rows']
  for mode,color in [('SCRATCH','#2563eb'),('PRIOR','#d97706')]:
   points=[r for r in rows if r.get('mode')==mode and r.get('repetition') in (1,3,5,8) and r.get('known_benefit_capture') is not None]
   points.sort(key=lambda r:r['repetition'])
   ax.plot([r['repetition'] for r in points],[r['known_benefit_capture'] for r in points],'o',label=mode,color=color)
  ax.axhline(0,color='#6b7280',lw=.8);ax.axhline(1,color='#9ca3af',ls='--',lw=.8)
  ax.set_xticks([1,3,5,8]);ax.set_title(title);ax.set_xlabel('Development attempt index (fresh segments)');ax.set_ylabel('Known-benefit capture (fraction)');ax.grid(alpha=.2);ax.legend()
 fig.suptitle('Verified same initial state; negative capture retained; invalid rep8 unavailable')
 finish(fig,'KNOWN_BENEFIT_CAPTURE_FIGURE')
 save(D/'FIGURE_PROVENANCE.json',{'status':'COMPLETE','source_files_sha256':{name:sha(D/name) for name in
  ('BEST_KNOWN_REFERENCE_TABLE.json','NATIVE_BEST_KNOWN_REFERENCE_TABLE.json','ALL_REFERENCE_SEARCH_CONVERGENCE.json','KNOWN_BENEFIT_CAPTURE.json','PRIMARY_OBJECTIVE_KNOWN_BENEFIT_CAPTURE.json')},
  'matplotlib_version':matplotlib.__version__,'figures_sha256':{p.name:sha(p) for p in D.glob('*_FIGURE.*')}})
if __name__=='__main__':main()
