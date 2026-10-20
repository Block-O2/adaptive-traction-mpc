from pathlib import Path
import os,json
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path'])
os.environ['MPLCONFIGDIR']=str(S/'control/matplotlib');os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,fontManager
fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc');plt.rcParams.update({'font.family':FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name(),'axes.unicode_minus':False,'font.size':11})
v=json.loads((S/'VALIDATION_RESULTS.json').read_text());fig,axes=plt.subplots(1,2,figsize=(14,6));rows=[r for r in v['rows'] if r['arm']=='frozen_best']
finite_gains=[r['gain_percent'] for r in rows if r['gain_percent'] is not None];foot=min(-.8,min(finite_gains,default=0)-.8)
labels={'velocity_deg_s/p95_abs':'速度95分位','velocity_deg_s/max_abs':'速度峰值','acceleration_deg_s2/p95_abs':'加速度95分位','acceleration_deg_s2/max_abs':'加速度峰值','endpoint_phase_boundary':'阶段端点差','excursion':'行程差','PRE_INTERVENTION_CAUSAL_CONTROL':'因果核验'}
for i,r in enumerate(rows):
    gain=r['gain_percent'];color='#287B68' if r['motion_pass'] else '#B7644F'
    if gain is None:axes[0].text(i,0,'完整成本\n不可评价',ha='center',va='bottom',color=color)
    else:
        axes[0].bar(i,gain,color=color,width=.58);axes[0].annotate(f'{gain:.3f}%\n'+('PASS' if r['motion_pass'] else 'FAIL'),(i,gain),xytext=(0,6),textcoords='offset points',ha='center',fontsize=10)
    fail=r['failed_requirements'];note=(labels.get(fail[0],fail[0])+'\n共'+str(len(fail))+'项失败') if fail else '完整比较通过'
    axes[0].text(i,foot,note,ha='center',va='top',fontsize=9)
axes[0].set_xticks(range(4),[r['condition'] for r in rows]);axes[0].axhline(0,color='#77818D',lw=1);axes[0].set_ylabel('相对本条件B的完整TASK累计力下降（%）');axes[0].set_ylim(bottom=foot-1.1,top=max(1,max(finite_gains,default=0))*1.35+.2);axes[0].set_title(f'冻结primary：合格 {v["primary_pass"]}/4，完整任务 {v["primary_complete_task_count"]}/4');axes[0].grid(axis='y',alpha=.15)
for item in v['real_boundary_states']:
    x=item['B_OUT_after_shared_prefix']
    if x:
        q=np.rad2deg(x['true_q_rad']);axes[1].scatter(q[0],q[1],s=85,color='#3D70A3');axes[1].annotate(item['condition'],q,xytext=(5,5),textcoords='offset points')
axes[1].set_xlabel('共享合法去程prefix后真实Hip（°）');axes[1].set_ylabel('共享合法去程prefix后真实Knee（°）');axes[1].set_title('由原动力学前向生成的四个状态');axes[1].grid(alpha=.15);axes[1].margins(x=.12,y=.12)
fig.suptitle('冻结后的预注册条件：收益与失败一同保留',fontsize=17)
fig.text(.5,.012,'同一已暴露Human；仅验证共享prefix后未消费策略。四条件分母固定；不能声称跨患者或整串原策略泛化。',ha='center',fontsize=10,color='#596470')
fig.tight_layout(rect=[0,.065,1,.91]);fig.savefig(S/'FIGURES/07_FROZEN_VALIDATION.png',dpi=160,bbox_inches='tight');plt.close(fig)
print('VALIDATION_FIGURE_WRITTEN')
