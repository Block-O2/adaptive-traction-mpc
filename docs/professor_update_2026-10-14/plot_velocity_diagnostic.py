"""Plot raw saved records and publish the narrow diagnostic in the current package."""
from pathlib import Path
import json,shutil,hashlib,re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from html.parser import HTMLParser
R=Path('/home/hank/coding/adaptive-traction-mpc-learning');D=R/'docs/professor_update_2026-10-14';W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/docs/professor_update_2026-10-14')
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/ihear_overnight_research_retrospective_v1');data=json.loads((D/'evidence/VELOCITY_DIAGNOSTIC_DATA.json').read_text());cases=data['cases']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'axes.labelsize':11,'path.simplify':False,'agg.path.chunksize':20000})
blue='#2376ad';orange='#d67532';purple='#8065a0';gold='#b8993e';gray='#65727d'
fig=plt.figure(figsize=(16,15),facecolor='white');gs=fig.add_gridspec(7,2,height_ratios=[1.15,1.15,.85,.95,.53,.9,.9],hspace=.42,wspace=.15)
axes=[]
for col,c in enumerate(cases):
 name=c['case'];z=np.load(P/'motion_series'/(name+'.npz'));tr=np.load(P/'source/results'/name/'trace.npz');t=z['time_s']-c['task_t0_absolute_s'];mask=tr['stage']=='TASK';ts=tr['time_s'][mask]-c['task_t0_absolute_s'];rv=np.degrees(tr['reference_dq_rad_s'][mask]);v=np.degrees(z['true_dq_rad_s']);acc=np.degrees(z['acceleration_rad_s2']);jerk=np.degrees(z['jerk_rad_s3'])
 ax=[fig.add_subplot(gs[row,col]) for row in range(7)];axes.append(ax)
 for row,j in [(0,0),(1,1)]:
  ax[row].plot(t,v[:,j],color=[blue,orange][j],lw=1.3)
  ax[row].step(ts,rv[:,j],where='post',color=gray,lw=1.1,ls='--')
  ax[row].set_ylabel(('Hip' if j==0 else 'Knee')+' velocity (deg/s)');ax[row].set_ylim(-30,30)
 ax[0].set_title(c['label']+' | full matched TASK',fontweight='bold',pad=24)
 for row,y,label,lim in [(2,acc,'Raw acceleration (deg/s²)',(-135,135)),(3,jerk,'Raw jerk (deg/s³)',(-20000,20000))]:
  ax[row].plot(t,y[:,0],color=blue,lw=.75,alpha=.95);ax[row].plot(t,y[:,1],color=orange,lw=.65,alpha=.88);ax[row].set_ylabel(label);ax[row].set_ylim(*lim)
 for row in range(4):
  a=ax[row];a.axvspan(9.005,10.025,color='#eaf0f2',zorder=0);a.axhline(0,color='#b8c1c9',lw=.55)
  for e in c['events']:
   if e['kind']=='activation':a.axvline(e['time_s'],color=purple,lw=.55,ls=':',alpha=.5,zorder=0)
   elif e['kind']=='suffix_effective':a.axvline(e['time_s'],color=gold,lw=.65,alpha=.5,zorder=0)
  a.set_xlim(0,19.03);a.grid(axis='y',alpha=.18);a.spines[['top','right']].set_visible(False)
  if row!=3:a.tick_params(labelbottom=False)
 ax[3].set_xlabel('Task elapsed simulation time (s)')
 for ph,x in [('OUTBOUND',4.5),('HOLD',9.515),('RETURN',14.5)]:ax[0].text(x,31.5,ph,ha='center',fontsize=10,color=gray)
 for row,j in [(0,0),(1,1)]:
  ext=next(e for e in c['extrema'] if e['signal']=='velocity_error_5ms' and e['joint']==['hip','knee'][j]);k=int(np.argmin(abs(ts-ext['time_s'])));sample=np.degrees(tr['evaluation_only_human_state_rad_rad_s'][mask,2:])[k,j]
  ax[row].plot(ext['time_s'],sample,'o',color=[blue,orange][j],ms=5)
  ax[row].annotate(f"max |true-ref|\n{ext['abs_value']:.2f} deg/s @ {ext['time_s']:.3f}s",xy=(ext['time_s'],sample),xytext=(ext['time_s']-1.8,20 if row==1 else 13),fontsize=9,arrowprops={'arrowstyle':'-','color':gray,'lw':.7},bbox={'facecolor':'white','edgecolor':'none','alpha':.86})
 # Actual receipt timestamps are a dense band, not fabricated sparse events.
 raster=ax[4]
 for kind,y,marker,color in [('request',3,'v',gray),('activation',2,'o',purple),('suffix_effective',1,'|',gold)]:
  tt=[e['time_s'] for e in c['events'] if e['kind']==kind];raster.scatter(tt,[y]*len(tt),s=20 if marker!='|' else 100,marker=marker,color=color)
 receipts=[r['time_s'] for r in c['receipts']];raster.scatter(receipts,np.zeros(len(receipts)),marker='|',s=7,color='#bcc7d0',alpha=.45)
 raster.set_yticks([0,1,2,3],['receipt','suffix','activation','request']);raster.set_xlim(0,19.03);raster.set_ylim(-.6,3.6);raster.spines[['top','right']].set_visible(False)
 # Zoom without smoothing: largest raw knee jerk, jointly with velocity.
 peak=next(e for e in c['extrema'] if e['signal']=='raw_jerk' and e['joint']=='knee');center=peak['time_s'];lo=center-.065;hi=center+.065;sel=(t>=lo)&(t<=hi);sr=(ts>=lo-.005)&(ts<=hi+.005)
 ax[5].plot(t[sel],v[sel,1],color=orange,lw=1.1);ax[5].step(ts[sr],rv[sr,1],where='post',color=gray,lw=1.1,ls='--');ax[5].set_ylabel('Knee velocity\nlocal raw (deg/s)');ax[5].set_title(f"Local view at max raw knee jerk: t={center:.4f}s",fontsize=11)
 ax[6].plot(t[sel],jerk[sel,1],color=orange,lw=1.0);ax[6].set_ylabel('Knee raw jerk\n(deg/s³)');ax[6].set_ylim(-20000,20000)
 for row in [5,6]:
  a=ax[row]
  for tt in receipts:
   if lo<=tt<=hi:a.axvline(tt,color='#bfc9d0',alpha=.5,lw=.5,zorder=0)
  for e in c['events']:
   if lo<=e['time_s']<=hi and e['kind'] in ['request','activation','suffix_effective']:
    a.axvline(e['time_s'],color={'request':gray,'activation':purple,'suffix_effective':gold}[e['kind']],lw=1.0,ls={'request':'--','activation':':','suffix_effective':'-'}[e['kind']])
  a.axvline(center,color=orange,ls='--',lw=.7);a.set_xlim(lo,hi);a.grid(axis='y',alpha=.18);a.spines[['top','right']].set_visible(False)
 ax[6].set_xlabel('Task time (s); pale ticks = applied-command receipts',fontsize=9)
 ax[6].text(.02,.08,'Peak precedes nearest new-plan activation by 9.5 ms;\nsecond derivative of raw native velocity, not a direct jerk sensor.',transform=ax[6].transAxes,fontsize=8.4,bbox={'facecolor':'white','edgecolor':'none','alpha':.85})
fig.suptitle('Velocity Smoothness Diagnostic — reference, physical response and handoffs',fontsize=18,fontweight='bold',y=.985)
legend=[Line2D([0],[0],color=blue,lw=2,label='True hip'),Line2D([0],[0],color=orange,lw=2,label='True knee'),Line2D([0],[0],color=gray,lw=1.3,ls='--',label='Logged reference (5 ms, ZOH display)'),Line2D([0],[0],color=purple,lw=1.2,ls=':',label='Recorded plan activation'),Line2D([0],[0],color=gold,lw=1.2,label='Recorded suffix effective')]
fig.legend(handles=legend,loc='upper center',bbox_to_anchor=(.5,.958),ncol=5,frameon=False,fontsize=10)
fig.subplots_adjust(left=.08,right=.98,top=.91,bottom=.07)
fig.text(.08,.022,'Raw physical velocity: 0.25 ms. Acceleration and jerk: unfiltered np.gradient, edge_order=2, matching archive exactly.\nFull series drawn; no smoothed replacement or interpolation of physical motion. Gray band: HOLD. Level 1 scientific simulation; no new rollout.',fontsize=10,color=gray)
fig.savefig(D/'assets/velocity_smoothness_diagnostic.png',dpi=190);plt.close(fig)
current=cases[1]
def eventcell(e):
 return f"{e['time_s']:.4f}s / {e['delta_ms']:+.2f}ms" if e else '无记录'
tabrows=[]
names={'velocity_error_5ms':'最大 |true − ref|','raw_acceleration':'最大 |raw acceleration|','raw_jerk':'最大 |raw jerk|'}
units={'velocity_error_5ms':'°/s','raw_acceleration':'°/s²','raw_jerk':'°/s³'}
for e in current['extrema']:
 tabrows.append([names[e['signal']]+' · '+e['joint'],f"{e['abs_value']:.3f} {units[e['signal']]}",f"{e['time_s']:.4f}",eventcell(e['nearest_activation']),eventcell(e['nearest_suffix']),eventcell(e['nearest_receipt'])])
table='| 指标 | 峰值 | TASK时刻 / s | 最近activation / Δt | 最近suffix / Δt | 最近receipt / Δt |\n|---|---:|---:|---|---|---|\n'+'\n'.join('| '+' | '.join(x.replace('|','\\|') for x in r)+' |' for r in tabrows)
md='''# Velocity Smoothness Diagnostic

本诊断复用本页 Baseline B 与 18D development best 的完整保存记录；新增物理运行 **0 次**。图见 `assets/velocity_smoothness_diagnostic.png`，精确事件、receipt ID、原始指标与来源哈希见 `evidence/VELOCITY_DIAGNOSTIC_DATA.json`。

## 速度变化集中在哪些时段？

去程、回程的分段加速/减速都可见速度起伏；HOLD（TASK 9.005–10.025 s）接近静止。对当前18D方案，最大膝速度偏差出现在去程终末制动 **7.000 s（9.542°/s）**，最大髋速度偏差出现在回程终末制动 **16.900 s（4.963°/s）**。Baseline 的对应最大偏差分别在7.430 s、17.055 s。这里“偏差”是同一5 ms时刻的true减reference，不把正常方向切换或设计加减速直接叫控制抖动。

## 更像参考变化，还是执行/接触响应？

两者都有，但应分两个尺度解释。较宽的速度波峰/波谷同时出现在参考与真实运动中：当前18D去程 hip/knee 相关系数0.994/0.983，回程0.990/0.991，支持主要运动形状与分段reference相关。相关系数不分解因果贡献。

终末制动时仍有明显true-reference偏差；18D膝最大偏差发生在最近suffix生效后 **230 ms**，髋最大偏差在suffix生效后 **360 ms**。这支持存在执行链、接触及闭环跟踪的动态响应，而不只是reference瞬时跳变。未做消融，不能把具体比例归因给cuff、动力学估计、低层控制或其他单一模块。

## 与handoff/scheduler切换有什么关系？

每组有14个已ACTIVATED计划、10个实际suffix splice。复合计划activation与suffix实际生效相隔约 **45 ms**，图中分别标注；request单独放在事件条。现存每组14份边界记录的q/dq jump为0，ddq最大绝对残差仅3.285×10⁻¹⁵ rad/s²（浮点舍入量级），满足原C2接续检查；这不要求速度在整段内恒定，也不保证实际Human同样平滑。

全程raw jerk峰值与5 ms命令receipt邻近：当前18D hip在3.0255 s、knee在5.6055 s，均在最近receipt后 **0.50 ms**，同时在最近新计划activation前 **9.50 ms**、suffix生效前 **54.50 ms**。因此不能把这些峰值解释为该新suffix生效时的瞬时抖动。每5 ms都有receipt，单次邻近不是因果证明；局部放大图只显示采样/命令时间结构与raw导数尖峰的关系。

## 能否说这是必须接受的结构代价？

**证据不足。更合适的表述是：部分跟踪指标改善，速度平滑性仍待优化。** 18D回程hip/knee速度误差RMS从Baseline的1.483/1.464降到1.234/1.270°/s；但去程hip RMS从0.943升至0.969°/s，膝最大偏差从9.166升至9.542°/s，hip raw jerk峰值从5548升至6697°/s³。不能称为全面改善或已解决。现有一对开发轨迹没有证明不可避免性、临床可接受性或其他结构无法更平顺。

## 当前18D最小时间关系表

所有时间均为TASK elapsed simulation time，Δt=峰值时刻−最近事件时刻；负数表示峰值在事件之前。“最近receipt”是实际command receipt，不是新计划事件。

'''+table+'''

## 数据与微分口径

- 每组真实q/dq完整覆盖19.03 s，76,121个native样本，步长0.25 ms；参考与共同时间的速度偏差使用3,807个5 ms trace样本，native true dq与同时间trace逐点吻合。
- 加速度从raw true dq用 `np.gradient(..., time_s, axis=0, edge_order=2)` 得到，jerk再用同一微分求得；两组数组与历史存档精确一致。它们是**数值导数暴露指标**，不是直接测得的加速度/jerk，不单凭尖峰大小宣称真实控制抖动或临床问题。端点使用单侧差分；表中峰值均不在端点差分区。
- 没有滤波、平滑或新插值。参考以5 ms采样的ZOH阶梯展示，不能据此把每个采样台阶说成连续quintic不光滑；raw真速度使用全部native点绘图。
- 记录边界的C2成立，不等于整个物理/执行链处处满足C2。图表只做解释性对齐，不修改原冻结motion规则；不重算/改选方案。科学仿真的simulation time与wall-clock source age严格分开，不用继承父运行的monotonic时钟冒充物理时间。
- 每组图中可读取的3,805条receipt来自原执行记录中因果命令baseline的contributions（含实际receipt index/time）；不是根据5 ms时钟人工生成，也不宣称完整导出了每个末端command。距离表使用这批可核验的实际receipt。
'''
(D/'VELOCITY_SMOOTHNESS_DIAGNOSTIC.md').write_text(md,encoding='utf-8')
htmlrows=''.join('<tr>'+''.join('<td>'+x+'</td>' for x in row)+'</tr>' for row in tabrows)
section='''<section id="velocity-diagnostic"><div class="number">APPENDIX / VELOCITY SMOOTHNESS DIAGNOSTIC</div><h2>Velocity Smoothness Diagnostic</h2><p class="lead">较宽速度起伏同时存在于 reference 与真实运动；终末制动有额外跟踪响应。记录的 C2 接续成立，仍不足以证明当前波动是必须接受的结构代价。</p><figure><img src="assets/velocity_smoothness_diagnostic.png" alt="Baseline 与18D的髋膝参考/真实速度、原始加速度和jerk、规划activation及suffix和receipt时间对齐诊断"><figcaption>全部0.25 ms真实速度与raw数值导数；参考5 ms采样，以ZOH展示。紫色点线为plan activation，金色实线为suffix实际生效；事件条分列request、activation、suffix和真实command receipt。最下方放大全程raw knee jerk峰值附近，无滤波。</figcaption></figure><div class="grid"><div class="card"><h3>波动与切换的位置</h3><p>当前18D最大膝速度偏差：去程7.000 s，9.542°/s；最大髋偏差：回程16.900 s，4.963°/s。分别在最近suffix生效后230/360 ms。HOLD 9.005–10.025 s接近静止。</p><p>两组各14个activation、10个实际suffix；activation与suffix相隔约45 ms。已记录q/dq边界jump为0，ddq残差仅浮点舍入量级，满足原C2检查；较宽分段速度变化仍可存在。</p></div><div class="card"><h3>原始jerk峰值怎样解释</h3><p>18D全程hip/knee raw jerk峰值分别在3.0255/5.6055 s：均在最近receipt后0.50 ms，却在最近新plan activation前9.50 ms、suffix生效前54.50 ms。</p><p>不能把它们归因于该新suffix的瞬时切换。jerk是raw速度的二次数值导数；命令receipt每5 ms都有，邻近本身不证明因果或真实控制抖动。</p></div></div><div class="table-wrap" style="margin-top:24px"><table><thead><tr><th>当前18D指标</th><th>峰值</th><th>TASK时刻 / s</th><th>最近activation / Δt</th><th>最近suffix / Δt</th><th>最近receipt / Δt</th></tr></thead><tbody>'''+htmlrows+'''</tbody></table></div><p class="sub" style="margin-top:12px">Δt = 峰值 − 最近事件；负数表示事件尚未发生。速度偏差用相同时刻5 ms样本；acceleration/jerk用完整raw native序列。图表未新增仿真。</p><div class="note">更合适的结论：<b>部分指标已改善，平滑性仍待优化。</b> 回程速度误差RMS下降；去程hip RMS、膝最大偏差和hip raw jerk峰值没有同步改善。没有证据证明这是不可避免的代价，也没有证明临床可接受性。</div><p><a href="VELOCITY_SMOOTHNESS_DIAGNOSTIC.md">简短诊断说明</a> · <a href="evidence/VELOCITY_DIAGNOSTIC_DATA.json">完整事件、指标与来源</a></p></section>
'''
html=(D/'index.html').read_text()
if 'id="velocity-diagnostic"' in html:html=re.sub(r'<section id="velocity-diagnostic">.*?</section>\n?',section,html,flags=re.S)
else:html=html.replace('<div class="footer">',section+'<div class="footer">',1)
if 'href="#velocity-diagnostic"' not in html:html=html.replace('<a href="#results">06 结果与限制</a>','<a href="#results">06 结果与限制</a><a href="#velocity-diagnostic">速度诊断</a>')
(D/'index.html').write_text(html,encoding='utf-8')
shutil.copy2('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/velocity_diagnostic_analyze.py',D/'diagnose_velocity_records.py');shutil.copy2('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/velocity_diagnostic_present.py',D/'plot_velocity_diagnostic.py')
manifest=[m for m in json.loads((D/'SOURCE_MANIFEST.json').read_text()) if m['file']!='evidence/VELOCITY_DIAGNOSTIC_DATA.json'];manifest.append({'file':'evidence/VELOCITY_DIAGNOSTIC_DATA.json','sha256':hashlib.sha256((D/'evidence/VELOCITY_DIAGNOSTIC_DATA.json').read_bytes()).hexdigest(),'source_package':str(P),'derivation':'read-only archived native traces, summaries and command receipts; no new run'})
(D/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2))
class Check(HTMLParser):
 def __init__(self):super().__init__();self.refs=[];self.ids=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.append(a['id'])
  for k in ['href','src','poster']:
   if k in a:self.refs.append(a[k])
c=Check();c.feed(html);missing=[ref for ref in c.refs if (ref.startswith('#') and ref[1:] not in c.ids) or (not ref.startswith('#') and not re.match(r'^[a-z]+:',ref) and not (D/ref).is_file())];assert not missing,missing
v=json.loads((D/'VERIFICATION.json').read_text());v.update(relative_resources_checked=len(c.refs),broken_relative_links=missing,velocity_diagnostic={'physics_runs_added':0,'native_derivatives_match_archive_exactly':True,'native_trace_velocity_alignment':True,'filtering':'none','figure_visual_check':'pending'});(D/'VERIFICATION.json').write_text(json.dumps(v,indent=2))
for name in ['index.html','SOURCE_MANIFEST.json','VERIFICATION.json','VELOCITY_SMOOTHNESS_DIAGNOSTIC.md','evidence/VELOCITY_DIAGNOSTIC_DATA.json','assets/velocity_smoothness_diagnostic.png','diagnose_velocity_records.py','plot_velocity_diagnostic.py']:shutil.copy2(D/name,W/name)
print('DIAGNOSTIC_READY',D/'assets/velocity_smoothness_diagnostic.png','STATIC_RESOURCES',len(c.refs),'PNG_BYTES',(D/'assets/velocity_smoothness_diagnostic.png').stat().st_size)
