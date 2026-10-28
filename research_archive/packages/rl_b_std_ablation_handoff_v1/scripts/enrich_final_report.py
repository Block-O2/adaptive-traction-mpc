"""Add directly measured complete-pair motion and timing tradeoffs to the report."""
from pathlib import Path
from research_common import ROOT,read,atomic,now

def main():
 p=ROOT/'REPORT.md';text=p.read_text();marker='## 完整等时pair的Human运动与执行年龄'
 if marker in text:text=text[:text.index(marker)].rstrip()+'\n'
 pairs=read(ROOT/'audit/PAIRED_COMPLETE_MOTION_TRADEOFFS.json')['pairs'];r=read(ROOT/'STD_ABLATION_RESULTS.json');lines=['',marker,'','仅下面3个同父、均完整且等时的pair可直接比较剂量。差值均为B−A；负tracking/jerk/overshoot代表该指标较小，不据此推断总体优越。','','|父seed|流|ΔJF N·s|ΔJM Nm·s|Δhip/knee tracking °|Δhip/knee jerk °/s³|ΔRETURN knee overshoot °|','|---|---|---|---|---|---|---|']
 for x in pairs:
  m=x['motion_difference_B_minus_A'];fmt=lambda a:'/'.join(f'{y:+.4f}' for y in a)
  lines.append(f'|{x["seed"]}|{x["rng"]}|{x["JF_difference_B_minus_A"]:+.6f}|{x["JM_difference_B_minus_A"]:+.6f}|{fmt(m["tracking_RMS_deg"])}|{fmt(m["jerk_RMS_deg_s3"])}|{m["RETURN_overshoot_below_goal_deg"][1]:+.4f}|')
 if all(x['JM_difference_B_minus_A']>0 for x in pairs):lines += ['', '这3个等时完整pair中B的JM均增加，JF方向不一致；因此“拒绝减少/完成数增加”不能解释为force、moment和Human运动的全面改善。']
 lines += ['', '|父seed/arm|planner实际source-age最大 ms（仿真时钟）|receipt实际source-age最大 ms（仿真时钟）|planner host activation-age最大 ms|receipt host apply-age最大 ms|TASK applied receipts|','|---|---|---|---|---|---|']
 for seed in [1495656323,1630784693]:
  for arm in ['A','B']:
   xs=[x for x in r['cases'] if x['seed']==seed and x['arm']==arm and x['split']=='preregistered']
   maxima=lambda key:max(x[key]['maximum'] for x in xs if x[key])
   lines.append(f'|{seed}/{arm}|{1000*maxima("request_physics_activation_age_s"):.6f}|{1000*maxima("source_age_TASK_s"):.6f}|{maxima("request_host_activation_age_ms"):.6f}|{maxima("receipt_host_sensor_age_at_apply_ms_profile"):.6f}|{sum(x["applied_receipts_TASK"] for x in xs)}|')
 lines += ['', '年龄来自保存request/receipt的不可变source sample与实际activation/apply时间戳，未用刷新样本伪装较低age。仿真与host时钟明确分开；以上不构成主机100ms硬实时或机器人硬件资格。全部实际6D torque和native归属留在各run的TASK_APPLIED_RECEIPTS_v2.npz及原raw。', '', '两父C以及所有B完整任务均为19.030秒；A完整任务另有19.075、19.135、19.335、19.625秒。其JF/JM全部列原值，未以跨时长差值宣称效率改善。', '', '准备过程还修正过零物理的路径、序列化和报告插入问题；2个实际物理job在native启动前失败的END另计，不算MuJoCo attempt。工程事件见audit/ENGINEERING_CORRECTIONS_LEDGER.json。']
 p.write_text(text+'\n'.join(lines)+'\n')
 print('measured complete-pair motion and actual timestamp-age tables added')
if __name__=='__main__':main()
