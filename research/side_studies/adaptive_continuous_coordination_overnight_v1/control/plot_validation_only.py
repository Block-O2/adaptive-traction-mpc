from pathlib import Path
import json,os
os.environ['MPLBACKEND']='Agg'
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[1]
new=json.loads((P/'BASELINE_REPRODUCTION.json').read_text())
history=json.loads((P/'audit/HISTORICAL_VALIDATION_RESULTS.json').read_text())
primary=[r for r in history['rows'] if r['arm']=='frozen_best']
fig,ax=plt.subplots(1,2,figsize=(12,5))
ax[0].bar(['Historical B','Historical 18D','New B repeat','New 18D repeat'],[1438.613498,1400.697221,new['runs'][0]['J_F_N_s'],new['runs'][1]['J_F_N_s']],color=['#486581','#d95f02','#486581','#d95f02']);ax[0].set_ylabel('Complete J_F (N s)');ax[0].set_ylim(0,1600);ax[0].tick_params(axis='x',rotation=18);ax[0].set_title('Known development state: exact numerical reproduction')
for i,r in enumerate(primary):
 ax[1].scatter(i,r['gain_percent'],marker='x',s=90,color='#c62828');ax[1].annotate('motion FAIL',(i,r['gain_percent']),xytext=(0,12),textcoords='offset points',ha='center',fontsize=9)
ax[1].set_xticks(range(4),[r['condition'] for r in primary]);ax[1].set_ylim(0,3.2);ax[1].set_ylabel('Force reduction vs matched B (%)');ax[1].set_title('HISTORICAL frozen primary: all-gate PASS 0/4')
ax[1].set_xlim(-.45,3.45)
for i,value in enumerate([1438.613498,1400.697221,new['runs'][0]['J_F_N_s'],new['runs'][1]['J_F_N_s']]):ax[0].text(i,value+25,f'{value:.3f}',ha='center',fontsize=9)
fig.suptitle('No new nonzero curve or new held-out validation in this campaign');fig.tight_layout();fig.savefig(P/'figures/development_and_historical_validation.png',dpi=160);plt.close(fig)
