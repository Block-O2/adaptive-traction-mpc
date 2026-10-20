from pathlib import Path
import os,json
W=Path(__file__).parent;S=Path(json.loads((W/'PACKAGE_LOCATION.json').read_text())['path']);F=S/'FIGURES'
os.environ['MPLCONFIGDIR']=str(S/'control/matplotlib');os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties,fontManager
fontManager.addfont('/mnt/c/Windows/Fonts/msyh.ttc');plt.rcParams.update({'font.family':FontProperties(fname='/mnt/c/Windows/Fonts/msyh.ttc').get_name(),'axes.unicode_minus':False,'font.size':11,'savefig.facecolor':'white'})
def load(p):return json.loads(p.read_text())
rows=[json.loads(x) for x in (S/'EVALUATIONS.jsonl').read_text().splitlines() if x.strip()]
dev=[r for r in rows if r['id'].startswith('development_repair2_')]
selection=load(S/'FROZEN_SELECTION.json') if (S/'FROZEN_SELECTION.json').exists() else None
best=selection['best'] if selection else min([r for r in dev if r['comparison']['acceptance_pass']],key=lambda r:r['J_F_N_s'])
base_id=best['base_id'];best_id=best['id'];label='冻结开发最好' if selection else '开发中暂时最好（未冻结验证）'
B=load(S/'reports'/(base_id+'_MEASURED.json'));M=load(S/'reports'/(best_id+'_MEASURED.json'))
def save(fig,name):fig.savefig(F/name,dpi=160,bbox_inches='tight');plt.close(fig)
teal='#287B68';gray='#77818D';red='#B7644F';blue='#3D70A3'
fig,axes=plt.subplots(1,2,figsize=(14,6),gridspec_kw={'width_ratios':[1.15,1]})
for ax in axes:
    for passed,color,name in [(True,teal,'冻结motion PASS'),(False,red,'motion FAIL，完整物理结果保留')]:
        rr=[r for r in dev if r['comparison']['acceptance_pass']==passed]
        ax.scatter([r['comparison']['gain_percent'] for r in rr],[r['constraints']['worst_ratio'] for r in rr],s=43,c=color,label=name,alpha=.75)
    ax.axhline(1,color=gray,lw=1.2,ls='--');ax.axvline(2,color=blue,lw=1,ls=':');ax.axvline(5,color=blue,lw=1,ls=':')
    ax.set_xlabel('相对同完整父开发B的累计力下降（%）');ax.set_ylabel('最严重冻结约束比（≤1才合格）');ax.grid(alpha=.16)
    ax.scatter([best['comparison']['gain_percent']],[best['constraints']['worst_ratio']],marker='*',s=220,c=blue,edgecolors='white',zorder=5)
axes[0].set_title('完整force—motion权衡');axes[0].legend(loc='upper left',fontsize=9)
axes[1].set_title('合格边界附近放大');axes[1].set_xlim(.4,max(3.5,best['comparison']['gain_percent']+.4));axes[1].set_ylim(.84,1.4)
fig.suptitle(f'{label}：{best["comparison"]["gain_percent"]:.4f}%；低力FAIL不升级为优质运动',fontsize=16)
fig.text(.5,.005,'本轮同条件开发数据。2%/5%是研究里程碑；motion阈值不是临床标准。数学提案拒绝与partial不参与此图。',ha='center',fontsize=9,color=gray)
fig.tight_layout(rect=[0,.035,1,.92]);save(fig,'04_FORCE_MOTION_TRADEOFF.png')

fig,axes=plt.subplots(2,2,figsize=(14,8),sharex=True)
for ident,name,color in [(base_id,'匹配B',gray),(best_id,label,teal)]:
    with np.load(S/'motion_series'/(ident+'.npz')) as z:
        t=z['time_s']-z['time_s'][0];q=np.rad2deg(z['true_q_rad']);v=np.rad2deg(z['true_dq_rad_s'])
    for joint in range(2):
        axes[0,joint].plot(t[::16],q[::16,joint],color=color,lw=1.4,label=name)
        axes[1,joint].plot(t[::16],v[::16,joint],color=color,lw=1.2,label=name)
    with np.load(S/'source/results'/ident/'trace.npz') as z:
        j=z['stage']=='TASK';tt=z['time_s'][j]-z['time_s'][j][0];ref=np.rad2deg(z['reference_q_rad'][j])
    for joint in range(2):axes[0,joint].plot(tt[::4],ref[::4,joint],color=color,lw=.85,ls='--',alpha=.55,label=name+' reference')
for joint,title in enumerate(['Hip','Knee']):
    axes[0,joint].set_title(title+'真实运动与发出参考');axes[0,joint].set_ylabel('角度（°）')
    axes[1,joint].set_title(title+'真实关节速度');axes[1,joint].set_ylabel('速度（°/s）');axes[1,joint].set_xlabel('TASK时间（s）')
for ax in axes.flat:
    ax.grid(alpha=.17);ax.axvspan(9.005,10.025,color=gray,alpha=.1)
handles,names=axes[0,0].get_legend_handles_labels()
fig.legend(handles,names,fontsize=9,loc='upper center',bbox_to_anchor=(.5,.94),ncol=2,frameon=False)
fig.suptitle('数学参考与真实人体执行分开记录',fontsize=17,y=.995)
fig.text(.5,.007,'真实q/dq来自完整0.25ms native运动；每16点显示一次，不滤波。验收统计用全部样本。灰带为B的HOLD区间。',ha='center',fontsize=9,color=gray)
fig.tight_layout(rect=[0,.035,1,.86]);save(fig,'05_ACTUAL_HUMAN_MOTION.png')

fig,axes=plt.subplots(1,2,figsize=(14,6),gridspec_kw={'width_ratios':[1.4,1]})
for ident,name,color in [(base_id,'匹配B',gray),(best_id,label,teal)]:
    with np.load(S/'source/results'/ident/'trace.npz') as z:
        j=z['stage']=='TASK';t=z['time_s'][j];f=np.linalg.norm(z['physical_cuff_force_world_n'][j],axis=1);cum=np.r_[0,np.cumsum(f[:-1]*np.diff(t))]
    axes[0].plot(t-t[0],cum,color=color,lw=1.8,label=f'{name}：{cum[-1]:.3f} N·s')
axes[0].set_xlabel('TASK时间（s）');axes[0].set_ylabel('累计物理cuff力积分（N·s）');axes[0].set_title('原TASK左积分口径');axes[0].legend(fontsize=10);axes[0].grid(alpha=.17)
phases=['OUTBOUND','HOLD','RETURN'];gains=[B['phase_cost']['phases'][p]['J_F_N_s']-M['phase_cost']['phases'][p]['J_F_N_s'] for p in phases]
bars=axes[1].bar(['去程','HOLD','回程'],gains,color=[blue,gray,teal]);axes[1].set_ylabel('相对B减少的J_F（N·s）');axes[1].set_title('实际phase边界分配');axes[1].axhline(0,color=gray,lw=.9)
for bar,g in zip(bars,gains):axes[1].annotate(f'{g:.6f}',(bar.get_x()+bar.get_width()/2,g),xytext=(0,5),textcoords='offset points',ha='center',fontsize=10)
fig.suptitle(f'完整任务下降 {B["J_F_N_s"]-M["J_F_N_s"]:.6f} N·s（{best["comparison"]["gain_percent"]:.4f}%）',fontsize=17)
fig.text(.5,.012,'没有删除HOLD或减少治疗动作。完整/phase积分闭合、真实motion与执行器合法性分别核验；仅LEVEL1科学研究。',ha='center',fontsize=9,color=gray)
fig.tight_layout(rect=[0,.05,1,.92]);save(fig,'06_CUMULATIVE_FORCE_AND_PHASES.png')
print('PHYSICAL_FIGURES_WRITTEN',best_id,len(dev),bool(selection))
