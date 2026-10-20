from pathlib import Path
import hashlib,json,ast
P=Path(__file__).resolve().parents[1];A=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_autonomous_review_v1');B='source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/'
rules=[('18D intent and velocity extension','code/rich_planner.py',1,60),('Original pass speed and target screening',B+'human_waypoint_feedback_mpc.py',184,351),('Original fixed-duration reference interface',B+'human_waypoint_scheduler.py',441,570),('Original tracking-offset screen',B+'full3d_adaptive_integration_v1/terminal_reference.py',309,359),('Current-state rolling admission',B+'full3d_adaptive_integration_v1/activation_validation.py',270,345),('Scientific source-age lifecycle',B+'full3d_adaptive_integration_v1/execution_policy.py',28,119),('Original future bridge and proposal',B+'full3d_adaptive_integration_v1/runtime_coordination_residual_v2.py',3150,3240)]
data=[];md=['# 原始源码执行规则（原文件SHA与逐行摘录）','这些是执行规则；不单独证明实际运动因果。新副本仅根路径迁移，身份在PREPHYSICAL_CHECKS中核对。']
for title,name,lo,hi in rules:
 f=A/name;lines=f.read_text().splitlines();hi=min(hi,len(lines));record=dict(title=title,source=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest(),start=lo,end=hi,numbered_excerpt='\n'.join(f'{i+1}: {lines[i]}' for i in range(lo-1,hi)))
 data.append(record);md+=['\n## '+title,f'`{f}:{lo}` SHA256 `{record["sha256"]}`','```python',record['numbered_excerpt'],'```']
(P/'provenance/SOURCE_RULES.json').write_text(json.dumps(data,indent=2)+'\n');(P/'provenance/SOURCE_RULES.md').write_text('\n'.join(md)+'\n')
tree=ast.parse((P/'control/terminal_repair.py').read_text());bad=[]
for n in ast.walk(tree):
 if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['mj_step','mj_step1','mj_step2','reset','forward']:bad.append(n.lineno)
 if isinstance(n,(ast.Assign,ast.AugAssign,ast.AnnAssign)):
  for target in n.targets if isinstance(n,ast.Assign) else [n.target]:
   if any(isinstance(x,ast.Attribute) and x.attr in ['qpos','qvel'] for x in ast.walk(target)):bad.append(n.lineno)
assert not bad
(P/'audit/INTERVENTION_SOURCE_GUARD.json').write_text(json.dumps(dict(status='PASS',scope='new intervention AST; original source semantics separately verified',no_human_state_assignment=True,no_physics_step_calls=True,forbidden=[]),indent=2)+'\n')
print('SOURCE_RULES',len(data))
