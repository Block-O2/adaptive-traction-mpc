"""Separate magnitude, direction and local residual descriptors at native cadence."""
from pathlib import Path
import json,math,datetime
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def read(n):return json.loads((P/n).read_text())
def norm(x):return math.sqrt(sum(float(v)**2 for v in x))
def measures(d):
 return dict(vector_rate_RMS=norm(d['vector_rate']['rms']),norm_rate_RMS=d['norm_rate']['rms'],vector_TV=d['TV_vector'],norm_TV=d['TV_norm'],local_vector_linear_residual_RMS_100ms=norm(d['local_linear_residual_100ms']['rms']),norm_RMS=d['norm']['rms'],norm_peak=d['norm']['peak_abs'])
pairs=[(i,'HANDOFF01_BEST','DEVELOPMENT') for i in ['HANDOFF01_BOTHLOW','OPT01_PATTERN011','COMPOSE01_PAIR01','STRICT01_REF025','STRICT01_ANT']]
val=read('analysis/LOCKED_VALIDATION_PAIRED_SUMMARY.json')
for r in val['rows']:
 if r['method'] in ['HANDOFF','PATTERN','COMPOSE','REFERENCE','ANTICIPATORY']:pairs.append((r['actual_id'],r['group']+'_BEST','FROZEN_LOCAL_PREFIX'))
rows=[]
for ident,baseline,split in pairs:
 r=read('attempts/'+ident+'_RESULT.json');b=read('attempts/'+baseline+'_RESULT.json');a=read('analysis/native_wrench/'+ident+'.json');base=read('analysis/native_wrench/'+baseline+'.json');entry=dict(id=ident,baseline=baseline,split=split,qualified_pair=bool(r['qualified'] and b['qualified']),cadence_s=.00025,JF_delta=r['JF']-b['JF'],JM_delta=r['JM']-b['JM'])
 e=read('analysis/extended/'+ident+'.json');be=read('analysis/extended/'+baseline+'.json');t=e['torque'];bt=be['torque']
 entry['control']=dict(applied_6D_rate_RMS_Nm_s=norm(t['applied_rate_nm_s']['rms']),baseline_applied_6D_rate_RMS_Nm_s=norm(bt['applied_rate_nm_s']['rms']),applied_6D_rate_RMS_change_percent=100*(norm(t['applied_rate_nm_s']['rms'])/norm(bt['applied_rate_nm_s']['rms'])-1),applied_rate_component_RMS_Nm_s=t['applied_rate_nm_s']['rms'],torque_clipping_samples=t['clipping_samples'],fallback_events=len(e['fallbacks']),rolling_splice_count=e['rolling_splice_count'],cadence_s=.005)
 entry['fixed_duration_cost_decomposition']=dict(duration_s=e['duration_s'],baseline_duration_s=be['duration_s'],original_mean_force_delta_N=(r['JF']-b['JF'])/e['duration_s'],original_mean_moment_delta_Nm=(r['JM']-b['JM'])/e['duration_s'],phase_JF_delta_Ns={ph:r['phase_cost'][ph]['J_F_N_s']-b['phase_cost'][ph]['J_F_N_s'] for ph in r['phase_cost']})
 for k in ['force','moment']:
  v=measures(a[k]);bv=measures(base[k]);entry[k]=dict(actual=v,baseline=bv,percent_change={key:100*(v[key]/bv[key]-1) for key in v})
 rows.append(entry)
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='EVALUATION_ONLY_COMPLETE',rows=rows,scope='Vector rate and norm rate are different physical descriptors. Local residual is a supplemental scalar statistic only, never a filtered replacement for original force, motion or integral. All original JF/JM remain 5ms left quadrature. Full primitive quantiles, component rates and peaks remain in native_wrench JSON.',new_physical_START=0)
(P/'analysis/WRENCH_COMPONENT_TRADEOFF.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
md='# 最高可得频率下的施力波动分量\n\nCONFIRMED：以下来自原执行链每0.25ms实际更新的缓存wrench，评估钩子不新增积分或observe。4kHz是此仿真已记录的最高频率；不能将它称为真实传感器带宽或连续时间峰值。早期仅有5ms的组不进入此表。原JF/JM仍用原5ms左积分。\n\n模长变化率与向量变化率不同；向量TV包含方向运动。100ms局部线性残差是独立统计量，其向量RMS合成为标量，并不是先滤掉尖峰后重评原运动。\n\n|身份|原合格对|力向量变化率RMS Δ%|力模长变化率RMS Δ%|力向量TV Δ%|力模长TV Δ%|力局部残差 Δ%|力RMS Δ%|力峰值 Δ%|力矩向量变化率RMS Δ%|力矩模长变化率RMS Δ%|\n|---|---|---|---|---|---|---|---|---|---|\n'
for r in rows:
 f=r['force']['percent_change'];m=r['moment']['percent_change'];values=[r['id'],'PASS' if r['qualified_pair'] else 'FAIL']+[f'{x:.5f}' for x in [f['vector_rate_RMS'],f['norm_rate_RMS'],f['vector_TV'],f['norm_TV'],f['local_vector_linear_residual_RMS_100ms'],f['norm_RMS'],f['norm_peak'],m['vector_rate_RMS'],m['norm_rate_RMS']]];md+='|'+'|'.join(values)+'|\n'
md+='\n每行相对同prefix强固定BEST。独立验证失败仍完整列出，不能把失败行当合格改善。合格配对均值与分母见FROZEN_VALIDATION_SUMMARY.md；这里显示个体结果，不拟合临床或跨患者分布。\n\nSUPPORTED：降低交接速度减少局部较快修正，但并不要求轨迹总变差、均值负荷和峰值同时降低。名义HANDOFF的力模长变化率下降约3%，其力TV却增加；因此“更平顺”必须说明具体指标。组合候选同时降低名义条件的向量／模长变化率、局部残差与TV，但平均负荷及JF上升，不能称全面更优。更小JM也不意味着所有瞬时力矩峰值更小。\n'
md+='\n## 实际执行器变化率与事件数量\n\n|身份|6轴applied torque变化率RMS N·m/s|相对BEST Δ%|clipping采样数|fallback事件数|rolling splice数|\n|---|---|---|---|---|---|\n'
for r in rows:
 c=r['control'];md+='|'+'|'.join([r['id'],f"{c['applied_6D_rate_RMS_Nm_s']:.6f}",f"{c['applied_6D_rate_RMS_change_percent']:.5f}",str(c['torque_clipping_samples']),str(c['fallback_events']),str(c['rolling_splice_count'])])+'|\n'
md+='\n此表使用原5ms实际applied torque，不能与4kHz wrench导数作相同带宽比较。名义交接、pattern及组合方案的6轴全局变化率RMS仅变化约+0.028%、−0.076%、−0.130%，远小于Human jerk的变化；因此不声称所有执行器波动均明显下降。三个方案的10次ESCAPE_ADMITTED和10次splice均保留，改善不能解释为减少这些安全执行事件的次数。\n'
md+='\nCONFIRMED：实际完整时长相同，原积分差精确对应时间平均负荷差：ΔJF=T·Δmean(F_norm)，ΔJM=T·Δmean(M_norm)。名义组合JF增加8.058633N·s，相当于原5ms均值增加约0.42347N；JM减少1.904880Nm·s，相当于均值减少约0.10010Nm。局部变化率／残差下降不会代数上强制均值下降。HYPOTHESIS：姿态负荷与力矩分配是均值取舍的物理解释，当前干预未分离所有机械分量，不能把整项变化唯一归因于某个分量。阶段原积分差逐项保留在JSON。\n'
(P/'WRENCH_COMPONENT_TRADEOFF.md').write_text(md);print('WRENCH_COMPONENT_SUMMARY',len(rows),'pairs')
