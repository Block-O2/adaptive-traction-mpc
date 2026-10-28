from pathlib import Path
import os,json
P=Path(__file__).resolve().parents[1];os.environ['MPLCONFIGDIR']=str(P/'runtime/tmp/mpl');import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
D=P/'figures';D.mkdir(exist_ok=True)
def read(n,d=None):
 f=P/n;return json.loads(f.read_text()) if f.exists() else d
def save(fig,name):
 fig.savefig(D/(name+'.png'),dpi=180,bbox_inches='tight');fig.savefig(D/(name+'.pdf'),bbox_inches='tight');plt.close(fig)
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
blend=read('analysis/BLEND_FIXED_CONFIRMATION_RESULTS.json',[])
if blend:
 fig,axes=plt.subplots(1,3,figsize=(12,3.6));labels=['Hip jerk RMS','Knee jerk RMS','Force magnitude rate RMS']
 for k,ax in enumerate(axes):
  x=np.arange(len(blend));ax.bar(x-.18,[-r['COMPOSE_vs_BEST_percent'][k] for r in blend],.36,label='COMPOSE');ax.bar(x+.18,[-r['BLEND_vs_BEST_percent'][k] for r in blend],.36,label='BLEND');ax.set_xticks(x,[r['group']+(' [BEST FAIL]' if not r['original_costs']['BEST']['qualified'] else '') for r in blend],rotation=20);ax.set_ylabel('Reduction vs BEST reference (%)');ax.set_title(labels[k]);ax.grid(axis='y',alpha=.2)
 axes[0].legend(frameon=False);fig.suptitle('Whole-policy physical simulation; failed reference explicitly retained');save(fig,'01_SMOOTHNESS_RETAINED')
e=read('analysis/COMBINED_FROZEN_RESULTS.json',{});rows=e.get('primary_rows',[])
if rows:
 fig,ax=plt.subplots(figsize=(11,4));keys=['A_FIXED_SMOOTH','B_HALF_SECOND','C_ONE_SECOND','D_CRITIC','FIXED_TRAINING_CHOICE'];labels=['Fixed COMPOSE','0.5 s','1.0 s','Critic','Training-fixed phase rule'];x=np.arange(len(rows));width=.15
 for j,(key,label) in enumerate(zip(keys,labels)):
  xs=x+(j-2)*width;vals=[]
  for r in rows:
   m=r['methods'][key];ref=r['methods']['E_REAL_FULL_REFERENCE'];vals.append(m['full_remaining_JF']-ref['full_remaining_JF'] if m['qualified'] else np.nan)
  bars=ax.bar(xs,vals,width,label=label)
  zero=[(xx,v) for xx,v in zip(xs,vals) if np.isfinite(v) and abs(v)<1e-10]
  if zero:ax.scatter([q[0] for q in zero],[q[1] for q in zero],s=24,color=bars[0].get_facecolor(),zorder=5)
  for xx,v in zip(xs,vals):
   if not np.isfinite(v):ax.text(xx,.02,'FAIL /\nabstain',rotation=90,fontsize=7,ha='center',va='bottom')
 ax.set_xticks(x,[r['group'] for r in rows]);ax.set_ylabel('Remaining JF regret (N s)');ax.grid(axis='y',alpha=.2);ax.legend(frameon=False,ncol=3,fontsize=8);ax.set_title('Frozen legal states: actual qualified finite-menu reference; dots mark zero regret');save(fig,'02_CRITIC_DECISION_VALUE')
s=read('analysis/PROSPECTIVE_SAMPLE_EFFICIENCY.json',{}).get('rows',[])
if s:
 fig,ax=plt.subplots(figsize=(9,4));x=np.arange(len(s));ax.bar(x-.18,[r['actual_unique_candidate_full_runs'] for r in s],.36,label='Actually executed candidate tails');ax.bar(x+.18,[r['exhaustive_unique_reference_candidate_runs'] for r in s],.36,facecolor='none',edgecolor='gray',hatch='///',label='Registered unique enumeration slots');ax.set_xticks(x,[r['group'] for r in s]);ax.set_ylabel('Complete candidate continuation count');ax.set_ylim(0,5);ax.legend(frameon=False,fontsize=8);ax.set_title('Pre-state traditional library screening; parent/B anchors paid separately');ax.text(.01,-.29,'Hatched slots in screened states were not run. Audit enumerates the actual full menu.\nTraining and audit overhead are included in total campaign cost; no net amortized saving claim.',transform=ax.transAxes,fontsize=8);save(fig,'03_PROSPECTIVE_ATTEMPTS')
print('FIGURES_SAVED',len(list(D.glob('*.png'))),flush=True)
