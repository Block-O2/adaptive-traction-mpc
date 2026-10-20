"""Relate frozen mathematical intent to activated schedules and actual receipts."""
from pathlib import Path
import json,os,sys,time,ast,hashlib
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import numpy as np
P=Path(__file__).resolve().parents[1]
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
parameters=read('FROZEN_18D.json')['free_parameters'];groups=['reproduction']+[r['name'] for r in read('RUN_PLAN.json')['validation_conditions']];allrows=[]
for g in groups:
 if not (P/(g+'_DONE.json')).exists():continue
 folder=P/'source/results'/(g+'_E');summary=json.loads((folder/'summary.json').read_text());line=read('reports/'+g+'_E_EXECUTED_RESIDUAL_RECEIPTS.json');by={r['decision_index']:r for r in line['rows']};rows=[]
 for lr in summary['learning_records']:
  meta=lr.get('selected_plan',{}).get('execution_screen',{}).get('free_trajectory')
  if meta is None:continue
  idx=lr['decision_index'];owned=by[idx];assert meta['parameters']==parameters,'FREE_PARAMETERS_CHANGED'
  rows.append(dict(decision_index=idx,phase=owned['phase'],free_intent=meta,activated=lr.get('selected_plan_activated'),actual_native_steps=owned['actual_native_steps'],first_execution_physics_s=owned['first_execution_physics_s'],actual_positive_receipt_count=len(owned['actual_command_receipts']),physically_executed=bool(meta['status']=='ACCEPTED' and lr.get('selected_plan_activated') and owned['actual_native_steps']>0)))
 assert rows and any(r['physically_executed'] for r in rows)
 with np.load(folder/'native_reference.npz') as z:
  refs=dict(path=str(folder/'native_reference.npz'),fields={k:list(z[k].shape) for k in z.files},sha256=hashlib.sha256((folder/'native_reference.npz').read_bytes()).hexdigest())
 context=read('audit/'+g+'_FORK_CONTEXT.json');fields={}
 with np.load(P/'source/results'/(g+'_B')/'trace.npz') as b,np.load(folder/'trace.npz') as a:
  ma=a['time_s']<=context['physical_s']+1e-9;mb=b['time_s']<=context['physical_s']+1e-9
  for k in a.files:
   if k in ['task_beta','task_residual_weights_nm']:
    amask=a['time_s'][a['stage']=='TASK']<=context['physical_s']+1e-9;bmask=b['time_s'][b['stage']=='TASK']<=context['physical_s']+1e-9
   else:amask,bmask=ma,mb
   x=a[k][amask];y=b[k][bmask];fields[k]=bool(x.shape==y.shape and (np.array_equal(x,y,equal_nan=True) if x.dtype.kind in 'fc' else np.array_equal(x,y)))
 assert all(fields.values()),'INHERITED_PREFIX_TRACE_MISMATCH'
 rec=dict(group=g,status='PASS',all_frozen_parameters_exact=True,richer_intent_decisions=len(rows),physically_executed_free_intent_decisions=sum(r['physically_executed'] for r in rows),rows=rows,issued_reference=refs,applied_command_and_ownership_source='reports/'+g+'_E_EXECUTED_RESIDUAL_RECEIPTS.json',inherited_prefix_trace_equality=fields,prefix_stop_physics_s=context['physical_s'],reference_is_not_human_motion=True)
 put('derived/'+g+'_INTENT_TO_EXECUTION.json',rec);allrows.append(rec)
index=[]
for name in ['code/rich_planner.py','code/runner.py','code/overnight_runner.py','code/search_driver.py','code/matched_harness.py','code/analyze_matched.py','code/explore_common.py','deps/coordination_adapter.py','deps/fork_core.py','source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/coordination_residual_v2.py']:
 f=P/name;tree=ast.parse(f.read_text());items=[dict(name=n.name,line=n.lineno,end=n.end_lineno) for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef))]
 index.append(dict(path=name,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),definitions=items))
put('audit/METHOD_SOURCE_INDEX.json',dict(files=index))
put('audit/INTENT_TO_ACTUAL_EXECUTION.json',dict(status='PASS',groups=allrows,scope='current activated free-intent metadata joined to original positive-step receipt intervals; emitted reference archived separately from actual Human native motion',physics_starts_added=0))
(P/'METHOD_AUDIT_DETAILS.md').write_text('''# 方法审计补充

18D更精确的分类是：**离线连续参数优化得到的固定waypoint参考意图，运行时按当前因果B目标作规则映射，再由原B重新规划和执行**。它不是整条固定参考或真实Human轨迹的回放；也不是直接优化整条连续时间曲线的控制器。连续空间系数影响在线生成的quintic及通过速度，但本轮没有增加或优化内部quintic控制点。

18项参数的单位均为无量纲：位姿系数作用于归一化任务进度，速度系数作用于原终端dq的比例。验证prefix是原K3接口的归一化action，乘原合同0.2变成差分进度；K3 knots为remaining progress的[0.1,0.4,0.7]。共享合同文件保留较早K2描述，TableInterface明确将K重设为3，不据文件字段误认本轮prefix为K2。

所有实际定义的精确行号与SHA见audit/METHOD_SOURCE_INDEX.json。数学意图、已激活schedule、issued reference、正native-step applied command及真实Human运动各有来源：derived/*INTENT_TO_EXECUTION列出每个free意图、ACCEPTED/REJECTED、activation和实际步数；native_reference/trace保存真正发出的q/dq/ddq；runtime_artifacts和原receipts保存实际torque与native ownership；motion_series由真实native qpos/qvel提取。参数相同不代表每一目标都被接纳，失败/回退仍由原B决定。

历史1376项manifest均实际核对通过。物理前已完成源文件与参数审阅、保护SHA、接口/数学预检和执行manifest冻结；对历史manifest全部条目的显式汇总核对是在复现运行期间补充完成，未发现差异。这一时序不冒称所有最终汇总文件均在第一START前生成。

数学公式、manifest与独立重算只分别证明对应合同，不能代替本轮新physics，也不能把scientific source-age资格升级为host-clock实时资格。独立计算脚本不等同独立人员或独立agent审查。
''')
print(json.dumps(dict(status='PASS',groups=len(allrows),executed=[r['physically_executed_free_intent_decisions'] for r in allrows])))
