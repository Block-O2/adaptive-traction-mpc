from audit_common import *
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
def main():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42})
 data=read(STUDY/'SCORE_DECOMPOSITION.json');states=data['states'];clock=read(STUDY/'EVENT_CLOCK_ALIGNMENT.json')['rows'];fig,axes=plt.subplots(len(states),1,figsize=(11,2.7*len(states)),layout='constrained',squeeze=False)
 for ax,state in zip(axes[:,0],states):
  row=next((r for r in state['rows'] if r.get('committed_valid')),None)
  if not row:continue
  origin=row['physical_start_s'];split=row['model_split_physical_clock_s']-origin;modelend=row['model_end_physical_clock_s']-origin;end=row['actual_end_physical_s']-origin
  intervals=[('Model near',0,split,'#287b99'),('Model V_base',split,modelend,'#c4864b'),('Online DeltaV: synthetic terminal',split,modelend,'#795594'),('True near at model clock split',0,min(split,end),'#568c7d'),('True full committed remainder',0,end,'#37816b')]
  match=next((r for r in clock if r['identity']==row['identity'] and r['event_match_available']),None)
  if match:
   actualsplit=match['actual_native_boundary_task_s']-row['model_origin_task_s']
   intervals.append(('Native MC label: actual - fresh model',actualsplit,end,'#577568'))
   ax.axvline(actualsplit,color='#37816b',linestyle='--',linewidth=.8)
  for y,(label,a,b,color) in enumerate(intervals):ax.barh(y,max(0,b-a),left=a,height=.55,color=color,alpha=.72)
  ax.set_yticks(range(len(intervals)),[r[0] for r in intervals]);ax.invert_yaxis();ax.axvline(split,color='#555',linestyle=':',linewidth=.8);ax.set_xlabel('Seconds from exact saved native boundary');ax.set_title(f'{state["state"]}: near split {split:.3f}s; model end {modelend:.3f}s; actual end {end:.3f}s');ax.grid(axis='x',alpha=.15)
 fig.suptitle('Aligned model, residual correction and physical cost intervals\nCorrection is a residual on V_base, not a second full cost; synthetic state differs from actual state',fontsize=11)
 for ext in ('png','pdf'):fig.savefig(STUDY/('COST_INTERVAL_ALIGNMENT.'+ext),dpi=170)
 plt.close(fig)
 fig,axes=plt.subplots(3,2,figsize=(11,10),layout='constrained');axes=axes.ravel()
 for ax,state in zip(axes,states):
  rows=state['rows'];x=np.arange(len(rows));width=.24
  for offset,mode,label,color in ((-width,'COMMITTED','Committed','#637a75'),(0,'P_RECEDING','P rolling','#267c9a'),(width,'PV_RECEDING','PV rolling','#825c9d')):ax.bar(x+offset,[r['mode_costs'].get(mode,np.nan) for r in rows],width,label=label,color=color,alpha=.82)
  ax.plot(x,[r['P_score'] for r in rows],'o--',color='#c38849',label='P forecast',markersize=4);ax.plot(x,[r['PV_score'] for r in rows],'s:',color='#ab5460',label='PV forecast',markersize=4)
  ax.set_xticks(x,[str(r['index'])+(' R' if not r['screening_accepted'] else '') for r in rows]);ax.set_title(state['state']);ax.set_ylabel('Remaining force integral (N s)');ax.grid(axis='y',alpha=.15)
 if len(states)<6:axes[-1].axis('off');axes[-1].legend(*axes[0].get_legend_handles_labels(),loc='center');axes[-1].text(.5,.2,'R: model screening rejected\nIndices/roles and validity: SCORE_DECOMPOSITION.json',ha='center',transform=axes[-1].transAxes)
 fig.suptitle('Frozen candidate consequences: committed versus actual rolling continuation',fontsize=12)
 for ext in ('png','pdf'):fig.savefig(STUDY/('CONTINUATION_COSTS.'+ext),dpi=170)
 plt.close(fig)
 if not (STUDY/'HUMAN_MODEL_ATTRIBUTION.json').exists():print('FIXED_POOL_FIGURES_SAVED; ATTRIBUTION_PENDING');return
 attribution=read(STUDY/'HUMAN_MODEL_ATTRIBUTION.json');fig,ax=plt.subplots(figsize=(8,4),layout='constrained');pairs=attribution['pairs'];x=np.arange(len(pairs));ax.bar(x-.18,[p['P_EST_J_F'] for p in pairs],.36,label='P_EST',color='#68818b');ax.bar(x+.18,[p['P_KNOWN_J_F'] for p in pairs],.36,label='P_KNOWN',color='#b4834c');ax.set_xticks(x,[p['kind']+' '+str(p['group']) for p in pairs]);ax.set_ylabel('Complete repetition force integral (N s)');ax.set_title('Paired effect of research Human parameter source');ax.legend(loc='upper left',bbox_to_anchor=(1.01,1));ax.grid(axis='y',alpha=.15)
 for ext in ('png','pdf'):fig.savefig(STUDY/('HUMAN_PARAMETER_ATTRIBUTION.'+ext),dpi=170)
 plt.close(fig);print('AUDIT_FIGURES_SAVED')
if __name__=='__main__':main()
