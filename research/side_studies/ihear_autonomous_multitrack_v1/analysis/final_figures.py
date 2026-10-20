from pathlib import Path
import json,shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
R=Path(__file__).resolve().parents[1]
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
rows=[r for r in json.loads((P/'EXPERIMENT_RESULTS.json').read_text())['rows'] if r['id'].startswith('Adev_')]
b=next(r for r in rows if r['id']=='Adev_B')
labels=[r['candidate']['id'] for r in rows]
colors=['#777777','#0072B2','#D55E00','#009E73','#CC79A7','#E69F00']
values=[[-r['motion']['gain_percent'] for r in rows],[100*(r['complete_metrics']['moment_integral_Nm_s']/b['complete_metrics']['moment_integral_Nm_s']-1) for r in rows],[r['motion']['excursion_delta_deg'][1] for r in rows]]
fig,axes=plt.subplots(1,3,figsize=(15,5.1),constrained_layout=True)
for ax,v,title,ylabel in zip(axes,values,['Full force cost','Full moment cost','Full knee excursion'],['J_F change vs matched B (%)','Moment integral change vs B (%)','Excursion minus matched B (deg)']):
 bars=ax.bar(labels,v,color=colors,width=.64)
 ax.axhline(0,color='#555555',lw=.7);ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True);ax.set_title(title);ax.set_ylabel(ylabel)
 ax.bar_label(bars,labels=[f'{x:+.3f}' for x in v],padding=4,fontsize=9)
 ax.tick_params(axis='x',labelsize=9)
axes[0].set_ylim(-2.8,.4);axes[1].set_ylim(0,8);axes[2].set_ylim(0,.67)
axes[2].axhline(.5,color='red',ls=':',label='Original +0.5 deg limit');axes[2].legend(loc='upper right',fontsize=8)
fig.suptitle('W1 full-task trade-offs: B qualifies; T, D, ER, AV090 and AV080 fail original motion gates')
name='force_motion_moment_tradeoff.png';fig.savefig(P/'figures'/name,dpi=150);plt.close(fig)
shutil.copy2(P/'figures'/name,R/'figures'/name)
print('FINAL_TRADEOFF_FIGURE_WRITTEN',flush=True)
