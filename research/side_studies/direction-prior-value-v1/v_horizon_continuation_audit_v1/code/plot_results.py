from freeze import *
import numpy as np
def main():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
 methods=['P','P+G','P+V','P+G+V'];colors=['#67717a','#247997','#cf8243','#77569a'];fig,axes=plt.subplots(3,2,figsize=(10,9),layout='constrained')
 for row,batch in enumerate(('final','independent','fresh')):
  a=json.loads((STUDY/f'ANALYSIS_v2_{batch}.json').read_text());lookup={(r['group'],r['method']):r for r in a['rows']};groups=sorted({r['group'] for r in a['rows']})
  for col,metric in enumerate(('J_F','moment_integral')):
   ax=axes[row,col]
   for x,method in enumerate(methods):
    changes=[]
    for group in groups:
     base=lookup.get((group,'P'));current=lookup.get((group,method))
     if base and current and base['valid'] and current['valid']:changes.append((base['metric'][metric]-current['metric'][metric])/base['metric'][metric]*100)
    if changes:
     ax.bar(x,np.mean(changes),width=.6,color=colors[x],alpha=.35)
     offset=np.linspace(-.16,.16,len(changes)) if len(changes)>1 else np.zeros(1);ax.scatter(x+offset,changes,s=22,color=colors[x],edgecolors='white',linewidths=.3,zorder=3)
    m=a['methods'][method];ax.text(x,.98,f'{m["valid"]}/{m["attempted"]}',ha='center',va='top',transform=ax.get_xaxis_transform(),fontsize=8)
   ax.axhline(0,color='#64717d',linewidth=.8);ax.set_xticks(range(4),methods);ax.set_ylabel('Paired reduction versus P (%)');ax.set_title(f'v2 {batch} — '+('Force integral' if col==0 else 'Moment integral'));ax.grid(axis='y',alpha=.18)
 fig.suptitle('Direction prior and long-horizon value: paired closed-loop outcomes\nDots: qualified pairs; bars: descriptive mean; counts: VALID / attempted',fontsize=12)
 fig.savefig(STUDY/'COMPARISON_PAIRED.png',dpi=180);fig.savefig(STUDY/'COMPARISON_PAIRED.pdf');plt.close(fig)
 synergy=json.loads((STUDY/'KNOWN_NONMYOPIC_ANALYSIS.json').read_text());fig,ax=plt.subplots(figsize=(8,4),layout='constrained');rows=synergy['rows'];x=np.arange(len(rows));width=.24
 for offset,key,label,color in ((-width,'benefit_vs_B_remaining_Ns','Measured full consequence','#247997'),(0,'P_predicted_benefit_Ns','P forecast','#cf8243'),(width,'PV_predicted_benefit_Ns','PV forecast','#77569a')):ax.bar(x+offset,[r[key] if r['qualified'] else np.nan for r in rows],width,label=label,color=color,alpha=.85)
 ax.set_xticks(x,[r['label']+('' if r['model_eligible'] else '\nmodel-filtered') for r in rows]);ax.axhline(0,color='#64717d',linewidth=.8);ax.set_ylabel('Remaining force-integral reduction vs B (N s)');ax.set_title('Fresh physical replay of the registered multi-step synergy design');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.15);fig.savefig(STUDY/'NONMYOPIC_CONSEQUENCES.png',dpi=180);fig.savefig(STUDY/'NONMYOPIC_CONSEQUENCES.pdf');plt.close(fig)
 print('SCIENTIFIC_FIGURES_SAVED')
if __name__=='__main__':main()
