from analyze_matched import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
def main():
 comparisons=load(S/'BIDIRECTIONAL_COMPARISON.json')['comparisons'];tags=['O','R','OR'];colors=['#3977A8','#4A9466','#A8773E'];fig,axs=plt.subplots(1,2,figsize=(11.6,4.8),layout='constrained')
 ax=axs[0];gains=[comparisons[t]['gain_percent'] for t in tags];bars=ax.bar(tags,gains,color=colors,width=.56);ax.axhline(.5,color='#B94743',ls='--',label='Preregistered discovery minimum (0.5%)');ax.set_ylim(0,.60);ax.set_ylabel('Full TASK force-integral reduction (%)');ax.set_title('Matched SCI: small positive force gains',loc='left',fontsize=12,fontweight='bold');ax.bar_label(bars,labels=[f'{g:.4f}%' for g in gains],padding=4);ax.legend(loc='upper left',fontsize=8,frameon=False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
 ax=axs[1];alltags=tags+['Frozen_M2'];metrics=[('velocity_deg_s/p95_abs','Speed'),('acceleration_deg_s2/p95_abs','Acceleration'),('jerk_deg_s3/p95_abs','Jerk')];x=np.arange(len(alltags))
 for i,(key,label) in enumerate(metrics):ax.bar(x+(i-1)*.23,[comparisons[t]['burden_ratios'][key][1] for t in alltags],width=.22,label=label,color=['#3977A8','#4A9466','#A8773E'][i])
 ax.set_xticks(x,tags+['Frozen M2']);ax.axhline(1.1,color='#B94743',ls='--',label='Research noninferiority limit (1.10)');ax.axhline(1,color='#666666',lw=.8);ax.set_ylabel('Raw knee p95 / matched B0');ax.set_title('Motion acceptance remains separate',loc='left',fontsize=12,fontweight='bold');ax.legend(fontsize=8,frameon=False);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
 for ax in axs:
  ax.spines[['top','right']].set_visible(False)
 fig.suptitle('B0 / OUTBOUND-only / RETURN-only / both phases',fontsize=15,fontweight='bold');fig.supxlabel('One existing Human setup; scientific numerical reproducibility, no held-out or host qualification.',fontsize=9)
 fig.savefig(S/'MATCHED_FORCE_MOTION.png',dpi=190);fig.savefig(S/'MATCHED_FORCE_MOTION.svg');plt.close(fig)
 print('PLOT_SAVED',flush=True)
if __name__=='__main__':main()
