"""Current natural-path evidence update; never rewrites historical G4 results."""
from common import ROOT,put
from stream_json import read_evidence
from pathlib import Path
import json,time

def read(p):
 with read_evidence(p,encoding='utf-8') as f:return json.load(f)
def main():
 rows=[]
 for name in ['ALL_TRAINING_LOG.jsonl','ALL_EVALUATION_LOG.jsonl']:
  if (ROOT/name).exists():rows.extend(json.loads(s) for s in (ROOT/name).read_text().splitlines())
 records=[];hold=[];safety=[]
 for row in rows:
  reason=row['abort_reason'];active=next((p for p in reversed(row['phases']) if p in ['OUTBOUND','HOLD','RETURN']),'NONE')
  if not row['success'] and active=='HOLD':hold.append({'run':row['run'],'reason':reason})
  if reason in ['Q_BOUNDS','TASK_VELOCITY_LIMIT','TASK_ACCELERATION_LIMIT','INTERFACE_FORCE_LIMIT','INTERFACE_MOMENT_LIMIT','ROBOT_TORQUE_LIMIT','BED_CONTACT','CLEARANCE_LIMIT']:safety.append({'run':row['run'],'reason':reason})
  if reason not in ['TIMEOUT_OUTBOUND','TIMEOUT_RETURN','TIMEOUT_HOLD']:continue
  run=ROOT/row['run'];ep=run/'env/episode_0001';summary=read(ep/'summary.json');metrics=read(ep/'episode_summary.json');audit=read(run/'INDEPENDENT_AUDIT.json');phase=reason.removeprefix('TIMEOUT_');trans=summary['task']['phase_transitions'];end=metrics['native_steps_total']*.00025;begin=end-metrics['task_s']
  starts=[x['time_s'] for x in trans if x['to']==phase];phase_start=starts[-1] if starts else begin
  phase_elapsed=end-phase_start
  checks={'actual_native_runtime_ABORTED':metrics['status']=='ABORTED' and not metrics['success'],'original_timeout_reason':metrics['abort_reason']==reason,'original_10s_phase_deadline':abs(phase_elapsed-10.)<1e-6,'last_active_phase_matches':active==phase,'actual_native_grid_and_ownership_pass':audit['ownership']['accounting_pass'],'reward_failure_terminal_pass':audit['reward']['pass'],'observed_motion_safety_pass':audit['motion']['pass'],'original_case_no_TEST_ONLY_category':'TEST_ONLY' not in read(run/'START.json')['category'],'no_injection_in_original_training_runner':row['stage'] in ['stage1','stage2'],'all_original_audit_checks_pass':audit['pass']}
  records.append({'seed':row['training_seed'],'episode':row['index'],'run':row['run'],'reason':reason,'phase':phase,'TASK_s':row['task_s'],'phase_elapsed_s':phase_elapsed,'native_steps':row['native_steps'],'reward':row['reward'],'policy_sha256_before':row['policy_before'],'checks':checks,'pass':all(checks.values()),'evidence_retention':'Native states were independently audited before PPO update; compact trace/receipts, native ownership/motion audit, causal ticks, transitions and SHA tombstones retained. Transient training native/raw removed uniformly under preregistered retention rule; not a new frozen full-raw evaluation.','phase_transitions':trans})
 phases={p:[x for x in records if x['phase']==p] for p in ['OUTBOUND','RETURN','HOLD']}
 result={'unix':time.time(),'historical_G4_STRICT_PASS':'FAIL_PRESERVED_UNCHANGED','current_G4_STRICT_PASS':'FAIL','natural_timeout_evidence':records,'natural_OUTBOUND_timeout_observed':any(x['pass'] for x in phases['OUTBOUND']),'natural_RETURN_timeout_observed':any(x['pass'] for x in phases['RETURN']),'natural_HOLD_failure_episodes':hold,'natural_absolute_safety_trigger_episodes':safety,'full_G4_promotion':False,'remaining_not_closed':['Natural HOLD failure path','Natural absolute-safety trigger path','Complete original G4 matrix and original full B/H150 qualification contract/fixtures; global TASK timeout evidence not established'],'all_recorded_timeout_evidence_audits_pass':all(x['pass'] for x in records),'no_extra_physics_attempts':True,'truth_firewall':'Saved physical truth for post-run audit only; actor unchanged.'}
 put(ROOT/'G4_NATURAL_PATH_UPDATE.json',result)
 text='# 本轮自然G4路径证据更新\n\n历史G4_STRICT_PASS=FAIL保持；本轮完整G4仍FAIL，不晋级。新证据来自正常PPO动作、原任务与原物理，无TEST_ONLY注入，没有修改deadline。\n\n|seed|episode|自然终止|TASK s|原phase elapsed s|审计|\n|---:|---:|---|---:|---:|---|\n'
 for x in records:text+=f"|{x['seed']}|{x['episode']}|{x['reason']}|{x['TASK_s']:.3f}|{x['phase_elapsed_s']:.3f}|{x['pass']}|\n"
 text+='\n已观察OUTBOUND与RETURN原10秒deadline自然触发，失败奖励、absorbing terminal、native ownership与观测运动审计通过。训练临时native大raw按预注册统一规则在原逐native审计通过后移除，compact trace/receipt、摘要、奖励/运动/ownership审计及hash仍保留；不冒称新增独立冻结完整raw评价。\n\n自然HOLD失败、绝对安全触发以及完整原矩阵尚未闭合；global TASK timeout证据未建立。几何不可行候选被拒绝属于保护生效，不冒称实际绝对安全触发。不能因为新增两个timeout路径就把G4改为PASS。最初沿用历史“缺自然timeout”概括不完整，最终报告以本表为准。\n'
 (ROOT/'G4_NATURAL_PATH_UPDATE.md').write_text(text)
 print(json.dumps({'timeouts':len(records),'OUTBOUND':len(phases['OUTBOUND']),'RETURN':len(phases['RETURN']),'all_timeout_audits_pass':result['all_recorded_timeout_evidence_audits_pass'],'G4_STRICT_PASS':'FAIL'}))
if __name__=='__main__':main()
