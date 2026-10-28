"""Paired locked-prefix summary; exact method aliases never create extra samples."""
from pathlib import Path
import os,sys,json,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def read(n):
 f=P/n;return json.loads(f.read_text()) if f.exists() else None
def stats(values):
 a=np.array(values,float);return None if not len(a) else dict(mean=float(a.mean()),min=float(a.min()),max=float(a.max()))
freeze=read('analysis/LOCKED_VALIDATION_SELECTION.json');records=[];methods={};complete=True;actual_ids=set()
for config in freeze['configs']:
 group=config['group'];cfg=read('experiments/'+group+'.json');baseline=read('attempts/'+group+'_BEST_RESULT.json');be=read('analysis/extended/'+group+'_BEST.json');bw=read('analysis/native_wrench/'+group+'_BEST.json')
 end=read('owned/'+group+'_SUPERVISOR_END.json');complete &= bool(end and end['worker_exit_code']==0)
 for method,tag in cfg['validation_method_aliases'].items():
  methods.setdefault(method,dict(expected=0,records=[]));methods[method]['expected']+=1;ident=group+'_'+tag;r=read('attempts/'+ident+'_RESULT.json');e=read('analysis/extended/'+ident+'.json');w=read('analysis/native_wrench/'+ident+'.json')
  if not r or not e or not w:complete=False;continue
  actual_ids.add(ident);record=dict(group=group,method=method,actual_id=ident,canonical_tag=tag,alias_shared=method!=tag,complete=r['complete'],qualified=r['qualified'],JF=r.get('JF'),JM=r.get('JM'),motion_worst_ratio=r.get('worst_ratio'),failed_motion=r.get('motion_vs_B',{}).get('failed_requirements',[]),native_jerk_RMS=e['native_motion']['jerk_deg_s3']['rms'],native_force_norm_rate_RMS=w['force']['norm_rate']['rms'],native_force_peak=w['force']['norm']['peak_abs'],native_force_RMS=w['force']['norm']['rms'],tracking_RMS_deg=e['tracking_RMS_deg'],native_velocity_peak=e['native_motion']['velocity_deg_s']['peak_abs'],native_acceleration_RMS=e['native_motion']['acceleration_deg_s2']['rms'],guard_active=e['guard']['active'],paired_original_qualified_vs_BEST=bool(r['qualified'] and baseline and baseline['qualified']))
  if be and bw:
   record['descriptive_change_vs_BEST']=dict(hip_jerk_RMS_pct=100*(record['native_jerk_RMS'][0]/be['native_motion']['jerk_deg_s3']['rms'][0]-1),knee_jerk_RMS_pct=100*(record['native_jerk_RMS'][1]/be['native_motion']['jerk_deg_s3']['rms'][1]-1),force_norm_rate_RMS_pct=100*(record['native_force_norm_rate_RMS']/bw['force']['norm_rate']['rms']-1),JF_delta_Ns=r['JF']-baseline['JF'],JM_delta_Nms=r['JM']-baseline['JM'])
  records.append(record);methods[method]['records'].append(record)
summary=[]
for method,info in methods.items():
 rr=info['records'];paired=[r for r in rr if r['paired_original_qualified_vs_BEST']];changes={key:stats([r['descriptive_change_vs_BEST'][key] for r in paired]) for key in ['hip_jerk_RMS_pct','knee_jerk_RMS_pct','force_norm_rate_RMS_pct','JF_delta_Ns','JM_delta_Nms']}
 summary.append(dict(method=method,expected_conditions=info['expected'],completed_conditions=len(rr),original_qualified_conditions=sum(r['qualified'] for r in rr),paired_qualified_vs_BEST_conditions=len(paired),qualified_paired_change=changes,failed_ids=[r['actual_id'] for r in rr if not r['qualified']],actual_ids=[r['actual_id'] for r in rr],alias_reused_result_count=sum(r['alias_shared'] for r in rr)))
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='FROZEN_VALIDATION_COMPLETE' if complete else 'RUNNING',same_Human_not_cross_patient=True,actual_unique_candidate_results=len(actual_ids),named_method_condition_rows=len(records),rows=records,method_summaries=summary,scope='Paired percentage/cost summaries require BOTH method and strongBEST original-qualified. Every failed completed row remains visible, and the paired sample count is explicit. Aliases share a single real result and are not independent samples. Four fixed local prefixes are not a statistical patient population.',new_physical_START=0)
(P/'analysis/LOCKED_VALIDATION_PAIRED_SUMMARY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
md='# 冻结独立prefix的配对结果\n\n状态：'+out['status']+'。同一Human，四个预登记局部prefix，不称跨患者泛化。所有方法、模型、source和四组配置在首次VAL前冻结，验证结果不回流调参。\n\n|方法|完成／预期|原合格|与BEST均合格对数|髋jerk RMS均值%|膝jerk RMS均值%|4kHz force-norm rate均值%|ΔJF均值N·s|ΔJM均值Nm·s|\n|---|---|---|---|---|---|---|---|---|\n'
for r in summary:
 def val(k):
  d=r['qualified_paired_change'][k];return '—' if d is None else f"{d['mean']:.6f}"
 md+='|'+'|'.join([r['method'],f"{r['completed_conditions']}/{r['expected_conditions']}",str(r['original_qualified_conditions']),str(r['paired_qualified_vs_BEST_conditions']),val('hip_jerk_RMS_pct'),val('knee_jerk_RMS_pct'),val('force_norm_rate_RMS_pct'),val('JF_delta_Ns'),val('JM_delta_Nms')])+'|\n'
md+='\n只对双方原合格的配对计算上表正式均值，分母明确列出；失败完整数据和描述性差值仍在JSON逐项保留。BO与HANDOFF冻结为相同动作，复用同一次实际验证，不增加物理尝试或样本。PPO只在VAL01／VAL03预登记评价，因此预期条件数为2；其他方法为4。原motion资格并不代表所有速度峰值、加速度RMS、force峰值／RMS均改善；逐项值见JSON与extended/native_wrench。\n\n不据四个确定性局部条件声称算法统计显著性或临床舒适度。完整原raw/scorer、冻结与来源hash、最高可得wrench、receipt/native及进程审计另附。\n'
(P/'FROZEN_VALIDATION_SUMMARY.md').write_text(md);print('LOCKED_PAIRED_SUMMARY',out['status'],'unique_actual',len(actual_ids),'named_rows',len(records))
