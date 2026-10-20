"""Standalone scientific figures from saved evidence, no physics."""
from task_bootstrap import *
import numpy as np
def main():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib.ticker import MaxNLocator
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':120,'savefig.dpi':180})
 folder=STUDY/'delivery/figures';folder.mkdir(parents=True,exist_ok=True);files=[]
 def finish(fig,name):
  fig.tight_layout();p=folder/(name+'.png');fig.savefig(p,bbox_inches='tight');plt.close(fig);files.append(dict(path=str(p),sha256=sha(p)))
 timing=json.loads((STUDY/'reports/REQUEST_TIMING_RECONCILIATION.json').read_text());selected=[]
 for id,req in [('000_T0_wall_B',6),('000_T0_wall_B',7),('117_host_cold_pair3_accelerated',6),('117_host_cold_pair3_accelerated',7)]:
  candidates=[r for r in timing['rows'] if r['id']==id and r['request_id']==req]
  if candidates:selected.append(candidates[0])
 categories=['capture / request','snapshot / handoff','worker queue','native worker','result collection','validation / command','apply / effective boundary'];colors=['#c0cad5','#6689b9','#bcb5de','#2f797b','#ddb569','#c67a69','#6d7988']
 def classify(s):
  a,b=s['start'],s['end']
  if a=='sensor_capture_ns':return 0
  if a in ('request_ns','snapshot_finish_ns'):return 1
  if a=='enqueue_ns':return 2
  if a=='worker_start_ns':return 3
  if a=='compute_finish_ns':return 4
  if a in ('result_collected_ns','validation_start_ns'):return 5
  return 6
 fig,ax=plt.subplots(figsize=(11,4.5))
 for i,r in enumerate(selected):
  sums=np.zeros(len(categories))
  for seg in r['event_intervals']:sums[classify(seg)]+=seg['ms']
  sums[-1]+=r['effective_activation_extra_ms'];left=0.
  for k,v in enumerate(sums):ax.barh(i,v,left=left,color=colors[k],height=.56,label=categories[k] if i==0 else None);left+=v
  ax.text(left+1,i,f'{r["age_ms"]:.2f} ms',va='center',fontsize=9)
 ax.set_yticks(range(len(selected)),['Original B / first','Original B / later','E5 Q worker / first (zero carry)','E5 Q worker / later (zero carry)'][:len(selected)])
 for x,label,color in [(40,'40 bridge duration*','#86622f'),(55,'strict <55 evaluator','#a63e3b'),(100,'100 generic expiry','#555')]:ax.axvline(x,color=color,ls='--',lw=1);ax.text(x,.99,label,transform=ax.get_xaxis_transform(),rotation=90,ha='right',va='top',fontsize=8)
 ax.set_xlim(0,115);ax.invert_yaxis();ax.set_xlabel('Immutable native source stamp → actual conservative activation (ms)');ax.set_title('Actual TASK activation: native admission is separate from strict eligibility');ax.legend(ncol=3,loc='lower center',bbox_to_anchor=(.5,-.48),frameon=False,fontsize=8);fig.text(.5,-.12,'*40 ms marks a duration scale only; the physical bridge clock and immutable source age have different origins.',ha='center',fontsize=8);finish(fig,'actual_activation_timeline')
 trade=json.loads((STUDY/'reports/SCIENTIFIC_FAST_BUDGET_SUMMARY.json').read_text()) if (STUDY/'reports/SCIENTIFIC_FAST_BUDGET_SUMMARY.json').exists() else None
 if trade is None:
  candidates=[p for p in (STUDY/'reports').glob('*TRADEOFF*')];assert len(candidates)==1;trade=json.loads(candidates[0].read_text())
 pairs=[]
 for prefix in ('180','184','188','192'):
  pair=[]
  for index in range(int(prefix),int(prefix)+4):
   p=next((STUDY/'output').glob(f'{index:03d}_FAST_BUDGET*_RESULT.json'));r=json.loads(p.read_text());assert r['metric']['valid'];pair.append(r['metric'])
  pairs.append(pair)
 fig,axs=plt.subplots(1,2,figsize=(11,4.5));labels=['Nominal seed 1','Nominal seed 2','Deviation A','Deviation B'];palette=['#777','#2f797b','#5689b6','#be9745'];x=np.arange(4);width=.18
 for j,label in enumerate(['B','6 candidates','4 candidates','2 candidates']):
  axs[0].bar(x+(j-1.5)*width,[p[j]['J_F'] for p in pairs],width,label=label,color=palette[j]);axs[1].bar(x+(j-1.5)*width,[p[j]['moment_integral'] for p in pairs],width,color=palette[j])
 for ax in axs:ax.set_xticks(x,labels,rotation=15,ha='right');ax.grid(axis='y',alpha=.2)
 axs[0].set_ylabel('Force integral J_F (N·s)');axs[1].set_ylabel('Moment integral (N·m·s)');fig.legend(*axs[0].get_legend_handles_labels(),frameon=False,fontsize=8,ncol=4,loc='upper center',bbox_to_anchor=(.5,.93));fig.suptitle('Frozen Q, SCI only: candidate count changes the computation–performance tradeoff');fig.subplots_adjust(top=.78);finish(fig,'candidate_budget_scientific')
 stable=json.loads((STUDY/'reports/CONTINUOUS_FROZEN_STABILITY_SUMMARY.json').read_text());fig,axs=plt.subplots(1,2,figsize=(10,4))
 for key,color,label in [('B','#777','B throughout'),('frozen','#2f797b','B Rep1, frozen Q thereafter')]:
  vals=[r[key+'_J_F'] for r in stable['rows']];axs[0].plot([1,2,3],vals[:3],'o-',color=color,label=label)
  bad=stable['rows'][3][key+'_failed_R2_cost_unranked'];axs[0].scatter([4],[bad],marker='x',s=75,color=color);axs[0].annotate('R2 invalid\nunranked',(4,bad),xytext=(-55,12),textcoords='offset points',fontsize=8,color=color)
  axs[1].plot([1,2,3,4],[r[key+'_phase_durations']['HOLD'] for r in stable['rows']],'o-',color=color)
 axs[1].axhline(1.020,color='#a63e3b',ls='--',label='unchanged upper bound');axs[0].set_ylabel('Force integral J_F (N·s)');axs[1].set_ylabel('HOLD duration (s)');axs[1].set_ylim(1.017,1.033)
 for ax in axs:ax.set_xlabel('Persistent native repetition');ax.xaxis.set_major_locator(MaxNLocator(integer=True));ax.grid(alpha=.2)
 axs[0].legend(frameon=False,fontsize=8);axs[1].legend(frameon=False,fontsize=8);fig.suptitle('Frozen SCI repetition stability: one plant, one belief updater, unchanged Q');finish(fig,'persistent_repetition_stability')
 resources=[];resource_groups={}
 for name in ('RESOURCE_LOG.jsonl','OFFLINE_RESOURCE_LOG.jsonl'):
  p=STUDY/'output'/name
  if p.exists():resource_groups[name]=[json.loads(line) for line in p.read_text().splitlines() if line.strip()];resources.extend(resource_groups[name])
 resources.sort(key=lambda r:r['unix']);t=np.asarray([(r['unix']-START)/3600 for r in resources]);gib=2**30
 fig,axs=plt.subplots(3,1,figsize=(11,7),sharex=True)
 axs[0].plot(t,[r['mem_available']/gib for r in resources],label='WSL MemAvailable',color='#2f797b')
 for name,color,label in [('RESOURCE_LOG.jsonl','#5689b6','Verified task PSS: runner/physics, then final sampler'),('OFFLINE_RESOURCE_LOG.jsonl','#be9745','Offline + verified runner descendants PSS')]:
  rs=resource_groups.get(name,[]);axs[0].plot([(r['unix']-START)/3600 for r in rs],[r['PSS']/gib for r in rs],label=label,color=color)
 axs[0].set_ylabel('GiB');axs[0].legend(frameon=False,ncol=1,fontsize=8)
 wins=[r for r in resources if r.get('windows') and 'commit_headroom' in r['windows']];tw=[(r['unix']-START)/3600 for r in wins]
 axs[1].plot(tw,[r['windows']['commit_headroom']/gib for r in wins],label='Windows commit headroom',color='#5689b6');axs[1].plot(tw,[r['windows']['available']/gib for r in wins],label='Windows available memory',color='#c67a69');axs[1].set_ylabel('GiB');axs[1].legend(frameon=False,ncol=2,fontsize=8)
 axs[2].plot(t,[r['swap_used']/2**20 for r in resources],label='Swap amount MiB',color='#be9745');axs[2].set_ylim(0,100);axs[2].set_ylabel('MiB');axs[2].legend(frameon=False,fontsize=8);axs[2].set_xlabel('Package elapsed wall time (hours)')
 for ax in axs:ax.grid(alpha=.2)
 fig.suptitle('Recorded resource windows (45 s cadence; early restart gap retained)');finish(fig,'resources')
 q=json.loads((STUDY/'reports/Q_CURRENT_COUNTERFACTUAL_AUDIT.json').read_text());coef=np.asarray(q['coefficient_tables_by_phase']);fig,axs=plt.subplots(1,2,figsize=(9,4));limit=np.max(np.abs(coef))
 for i,ax in enumerate(axs):
  im=ax.imshow(coef[i],cmap='RdBu_r',vmin=-limit,vmax=limit,aspect='auto');ax.set_xticks([0,1,2],['K3 node 1','K3 node 2','K3 node 3']);ax.set_yticks(range(5),[f'Plan slot {j+1}' for j in range(5)]);ax.set_title(['OUTBOUND','RETURN'][i])
  for j in range(5):
   for k in range(3):ax.text(k,j,f'{coef[i,j,k]:.1f}',ha='center',va='center',color='white' if abs(coef[i,j,k])>.55*limit else '#222',fontsize=8)
 fig.colorbar(im,ax=axs.ravel().tolist(),fraction=.025,pad=.08,label='Fixed unscaled plan coefficient (N·s)');fig.suptitle('Linear Q has fixed plan coefficients and no state × plan interaction');fig.subplots_adjust(top=.8,bottom=.15,right=.84,wspace=.35);p=folder/'linear_Q_plan_coefficients.png';fig.savefig(p,bbox_inches='tight');plt.close(fig);files.append(dict(path=str(p),sha256=sha(p)))
 legal=json.loads((STUDY/'reports/LEGAL_PREFIX_STABILITY_SUMMARY.json').read_text());assert legal['valid_pairs']==8 and all(r['matched_pre_learning_prefix_proof']['status']=='PASS' for r in legal['rows'])
 fig,axs=plt.subplots(1,2,figsize=(10,4.5),sharey=True);x=np.arange(8)
 for ax,key,color,title in [(axs[0],'paired_force_reduction_percent','#2f797b','Force integral reduction vs matched B'),(axs[1],'paired_moment_increase_percent','#c67a69','Moment integral increase vs matched B')]:
  values=[r[key] for r in legal['rows']];ax.barh(x,values,color=color,height=.65);ax.set_xlim(0,max(values)*1.2);ax.set_xlabel('Paired difference (%)');ax.set_title(title,fontsize=10);ax.grid(axis='x',alpha=.2)
  for j,value in enumerate(values):ax.text(value+.15,j,f'{value:.2f}%',va='center',fontsize=8)
 axs[0].set_yticks(x,[f'Prefix pair {r["pair"]}' for r in legal['rows']]);axs[0].invert_yaxis();fig.suptitle('Eight preregistered legal-prefix pairs: frozen Q, SCI only, exposed nominal Human');finish(fig,'legal_prefix_stability')
 sources=[STUDY/'reports'/name for name in ('REQUEST_TIMING_RECONCILIATION.json','CONTINUOUS_FROZEN_STABILITY_SUMMARY.json','Q_CURRENT_COUNTERFACTUAL_AUDIT.json','SCIENTIFIC_CANDIDATE_TRADEOFF_SUMMARY.json','LEGAL_PREFIX_STABILITY_SUMMARY.json')]+[STUDY/'output'/name for name in ('RESOURCE_LOG.jsonl','OFFLINE_RESOURCE_LOG.jsonl')]
 save(STUDY/'delivery/FIGURE_MANIFEST.json',dict(status='GENERATED_PENDING_VISUAL_QA',figures=files,inputs={str(p):sha(p) for p in sources if p.exists()},physics_added=0));print(json.dumps(dict(figures=files)))
if __name__=='__main__':main()
