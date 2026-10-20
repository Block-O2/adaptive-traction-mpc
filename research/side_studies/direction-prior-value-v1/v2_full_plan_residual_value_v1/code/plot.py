from common import *
import numpy as np
def main():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
 gate=read(NEW/'ORACLE_GATE.json');states=gate['states'];fig,axes=plt.subplots(1,2,figsize=(11,4.6),layout='constrained');x=np.arange(len(states));width=.25
 for ax,contract in zip(axes,('ROLLING_P','COMMITTED')):
  for offset,label,key,color in ((-width,'P','P','#387f96'),(0,'P + V1','P_V1','#86649d'),(width,'P + oracle','P_ORACLE','#64816a')):ax.bar(x+offset,[s['comparisons'][contract][key]['accepted_pool_regret'] for s in states],width,label=label,color=color)
  ax.set_xticks(x,[s['state'] for s in states],rotation=25,ha='right');ax.set_ylabel('Accepted-pool selected-action regret (N s)');ax.set_title(contract+(' (PRIMARY)' if contract=='ROLLING_P' else ' (diagnostic)'));ax.grid(axis='y',alpha=.15);ax.set_ylim(bottom=0,top=max(1.,max(s['comparisons'][contract]['P_V1']['accepted_pool_regret'] for s in states)*1.2));ax.legend(fontsize=8)
 fig.suptitle('Mandatory offline oracle gate: primary correction has zero top-1 gain\n15 frozen candidates / 5 native parent states; hard screens retained',fontsize=12)
 for ext in ('png','pdf'):fig.savefig(NEW/('ORACLE_GATE_REGRET.'+ext),dpi=170)
 plt.close(fig)
 decomposition=read(NEW/'FULL_PLAN_ERROR_DECOMPOSITION.json');fig,axes=plt.subplots(1,2,figsize=(11,5),layout='constrained');colors=['#3a8099','#ba965b','#7b6a91']
 for ax,c in zip(axes,('COMMITTED','ROLLING_P')):
  x=np.arange(len(decomposition['rows']));positive=np.zeros(len(x));negative=np.zeros(len(x))
  for k,color in zip(('OUTBOUND','HOLD','RETURN'),colors):
   value=np.array([r['residual_by_phase'][c][k] for r in decomposition['rows']]);bottom=np.where(value>=0,positive,negative);ax.bar(x,value,bottom=bottom,label=k,color=color);positive+=np.maximum(value,0);negative+=np.minimum(value,0)
  ax.axhline(0,color='#555',linewidth=.7);ax.set_xticks(x,[r['state'][:3]+str(r['index']) for r in decomposition['rows']],rotation=75,ha='right',fontsize=8);ax.set_ylabel('Actual - full model remaining cost (N s)');ax.set_title(c);ax.grid(axis='y',alpha=.15)
 axes[0].legend(fontsize=8);fig.suptitle('Full-plan residual components by physical task phase\nROLLING_P includes model error and frozen-P continuation effect',fontsize=12)
 for ext in ('png','pdf'):fig.savefig(NEW/('FULL_PLAN_RESIDUAL_PHASES.'+ext),dpi=170)
 plt.close(fig);print('SCIENTIFIC_FIGURES_SAVED')
if __name__=='__main__':main()
