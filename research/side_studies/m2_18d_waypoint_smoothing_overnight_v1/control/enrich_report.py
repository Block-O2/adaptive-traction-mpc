"""Final data-driven four-group figure and mechanism detail, zero physics."""
from pathlib import Path
import os,sys,json,shutil
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MPLBACKEND='Agg')
P=Path(__file__).resolve().parents[1];L=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc')/P.name;sys.path[:0]=[str(P/'control'),str(P/'code')]
from postprocess_targeted import load
from analyze_mechanism import put
import numpy as np,matplotlib.pyplot as plt
rows=json.loads((P/'ALL_ANALYZED_RESULTS.json').read_text())['rows'];lookup={r['id']:r for r in rows};interactions=[]
fig,axs=plt.subplots(6,1,figsize=(16,18),sharex=True,layout='constrained')
for ident,label,color,style in [('development2_B0','B','#2166ac','-'),('development2_E0','18D','#b2182b','-'),('development2_B_OR_smooth','B+S (O+R)','#67a9cf','--'),('development2_E_OR_smooth','18D+S (O+R)','#ef8a62','--')]:
 r=lookup[ident];assert r['status']=='COMPLETE';z=load(ident)
 axs[0].plot(z['tf'],z['f'],c=color,ls=style,label=label);axs[1].plot(z['tf'],z['cf'],c=color,ls=style)
 for j in range(2):
  axs[2+j].plot(z['t'][::10],np.degrees(z['v'][::10,j]),c=color,ls=style,label=label+' actual');axs[2+j].plot(z['tf'],np.degrees(z['refv'][:,j]),c=color,ls=':',alpha=.55)
 if r['candidate'].get('changes'):
  b=load(r['matched_baseline']);axs[4].plot(z['tf'],z['cf']-b['cf'],c=color,ls=style,label=label+' minus its base')
  delta=np.cumsum(np.linalg.norm(np.diff(z['v'],axis=0),axis=1)-np.linalg.norm(np.diff(b['v'],axis=0),axis=1));axs[5].plot(z['t'][1:][::20],delta[::20],c=color,ls=style)
for base in ['B','E']:
 single=[lookup['development1_'+base+'_'+phase+'_smooth'] for phase in ['O','R']];combined=lookup['development2_'+base+'_OR_smooth']
 interactions.append(dict(base=base,combined_delta=combined['full_J_F_delta'],sum_single_delta=sum(r['full_J_F_delta'] for r in single),interaction_delta=combined['full_J_F_delta']-sum(r['full_J_F_delta'] for r in single),full_TV_change_percent=combined['full_TV_v_change_percent'],scope='within-base O/R total effects; base-specific shapes do not identify an identical-S factorial interaction'))
labels=['Force [N] at 5ms','Cumulative J_F [N s]','Hip v [deg/s], dotted ref','Knee v [deg/s], dotted ref','Cumulative ΔJ_F [N s]','Cumulative ΔTV_v [rad/s]']
for ax,label in zip(axs,labels):
 ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(0,19.03)
 for t in [9.005,10.025]:ax.axvline(t,c='.5',lw=.7)
axs[0].legend(ncol=4);axs[4].legend();axs[-1].set_xlabel('Task elapsed [s]; absolute = task + 10.05 s');fig.suptitle('Four groups, identical task duration | base-specific targeted S, no universal synergy claim')
fig.savefig(P/'figures/four_group_comparison.png',dpi=150);plt.close(fig);put('derived/COMBINATION_INTERACTIONS.json',dict(rows=interactions))
repeat=json.loads((P/'REPEAT_GATES.json').read_text());down=json.loads((P/'derived/DOWNSTREAM_ACCOUNTING.json').read_text())['rows'];counter=next(r for r in down if r['id']=='development1_E_R_smooth');demand=json.loads((P/'derived/NEW_DEMAND_DECOMPOSITION.json').read_text())['rows'];d=next(r for r in demand if r['id']==counter['id'])['windows']['0.000000-19.030000']
text=f'''\n## 本轮关键反例、重复与组合

18D回程平滑support内ΔJ_F={counter['support_delta_N_s']:+.9f} N·s，support外={counter['outside_support_delta_N_s']:+.9f}，完整={counter['full_delta_N_s']:+.9f}。已存档的request时刻/执行标签变化数量={len(counter['schedule_changes'])}；没有据此把抵消归为重规划时序改变。原纯allocator重算完整差={d['pure_allocator_delta_N_s']:+.9f} N·s，实测差={d['measured_delta_N_s']:+.9f}；模型姿态需求、tracking、robot/contact响应仍共同参与，独立smoothness中介未识别。

两个batch的B/18D及18D去/回程smooth重复均比较了全部trace、116320 native行和5817 receipts，结果{repeat['status']}。两批来自不同冷父进程，完整fork hash的跨批相等情况逐例保存；只声明同开发条件的确定性物理重复，不称相同父进程或新prefix验证。

|base|O+R完整ΔJ_F N·s|单独O/R差值之和|组合交互差|完整TV_v变化%|
|---|---:|---:|---:|---:|
'''+''.join(f"|{r['base']}|{r['combined_delta']:+.9f}|{r['sum_single_delta']:+.9f}|{r['interaction_delta']:+.9f}|{r['full_TV_change_percent']:+.4f}|\n" for r in interactions)+'''
交互差为ΔJ_OR−ΔJ_O−ΔJ_R，负值表示额外降力。它只描述本base的O/R组合；B与18D使用各自设计的S，不能将两者差异解释为相同处理的纯因果synergy。

![四组共同时间轴](figures/four_group_comparison.png)

![局部与下游累计变化](figures/downstream_cumulative_effects.png)
'''
with (P/'REPORT.md').open('a',encoding='utf-8') as f:f.write(text)
with (P/'FORCE_MOTION_DIAGNOSTIC.md').open('a',encoding='utf-8') as f:f.write(text)
with (P/'HISTORICAL_18D_MECHANISM.md').open('a',encoding='utf-8') as f:f.write('\n本轮另运行原纯allocator需求分解的独立代数重算，结果见derived/DEMAND_TERM_DECOMPOSITION.json，未增加physics：gravity −18.137642、elastic −30.621873、velocity terms −0.035799、remainder +1.225298、allocation geometry +11.042477 N·s，合计−36.527540。该恒等分解与既有报告一致；没有重跑物理消融或把比值当因果中介份额。\n')
for n in ['REPORT.md','FORCE_MOTION_DIAGNOSTIC.md','HISTORICAL_18D_MECHANISM.md']:shutil.copy2(P/n,L/n)
shutil.copy2(P/'figures/four_group_comparison.png',L/'figures/four_group_comparison.png');shutil.copy2(P/'derived/COMBINATION_INTERACTIONS.json',L/'derived/COMBINATION_INTERACTIONS.json')
print(json.dumps(interactions,indent=2))
