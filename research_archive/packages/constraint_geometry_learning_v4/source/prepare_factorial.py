from pathlib import Path
import json,copy,datetime
P=Path(__file__).resolve().parents[1]
s=(P/'source/acl2_modal_retimed.py').read_text().replace('class RetimedModalPlanner','class FactorialModalPlanner')
s=s.replace('shift[endpoint_locked]=0.',"if getattr(self,'permission_endpoint_lock',True):shift[endpoint_locked]=0.")
s=s.replace('proxy=ReplanDuration(native,old.duration_s,factor);self.scheduler=proxy;self.round_forced_velocity=velocity',"proxy=ReplanDuration(native,old.duration_s,factor) if getattr(self,'permission_duration_floor',True) else FixedDuration(native,duration);self.scheduler=proxy;self.round_forced_velocity=velocity")
s=s.replace('scheduler_duration_record=proxy.record',"permission_endpoint_lock=bool(getattr(self,'permission_endpoint_lock',True)),permission_duration_floor=bool(getattr(self,'permission_duration_floor',True)),scheduler_duration_record=getattr(proxy,'record',None)")
(P/'source/factorial_planner.py').write_text(s)
w=(P/'source/v4_worker.py').read_text().replace('from acl2_modal_retimed import RetimedModalPlanner','from acl2_modal_retimed import RetimedModalPlanner\nfrom factorial_planner import FactorialModalPlanner')
w=w.replace("in ['modal8','modal8_retimed']:","in ['modal8','modal8_retimed','factor8']:")
w=w.replace("b['planner'].__class__=RetimedModalPlanner if self.active_action.get('family')=='modal8_retimed' else ModalPlanner;b['planner'].coordination_modes=np.asarray(self.active_action['x'],float);b['planner'].coordination_slot=slot", "b['planner'].__class__=FactorialModalPlanner if self.active_action.get('family')=='factor8' else RetimedModalPlanner if self.active_action.get('family')=='modal8_retimed' else ModalPlanner;b['planner'].coordination_modes=np.asarray(self.active_action['x'],float);b['planner'].coordination_slot=slot\n    b['planner'].permission_endpoint_lock=bool(self.active_action.get('endpoint_lock',True));b['planner'].permission_duration_floor=bool(self.active_action.get('duration_floor',True))")
w=w.replace("'branch_diagnostics.py']","'branch_diagnostics.py','factorial_planner.py']")
(P/'source/v4_factor_worker.py').write_text(w)
sup=(P/'source/supervise.py').read_text().replace("str(P/'source/v4_worker.py')","str(P/'source'/c.get('worker','v4_worker.py'))")
(P/'source/supervise_v2.py').write_text(sup)
cfg=json.loads((P/'experiments/DEV.json').read_text());by={x['tag']:x['action'] for x in cfg['actions']};cfg.update(group='FACT',historical_repeats={},actions=[],worker='v4_factor_worker.py',job_wall_cap_s=5400);cfg['condition']['name']='FACT'
cfg['actions'].append(dict(tag='B',action=by['B'],category='factorial_reference'))
for name in ['BEST','C19']:
 for lock,floor in [(0,0),(1,0),(0,1),(1,1)]:
  action=copy.deepcopy(by[name]);action.update(family='factor8',endpoint_lock=bool(lock),duration_floor=bool(floor));cfg['actions'].append(dict(tag=f'{name}_L{lock}_D{floor}',action=action,category='permission_factorial'))
for n in ['experiments/FACT.json','runtime/FACT_TEST_PLAN.json']:(P/n).write_text(json.dumps(cfg,indent=2)+'\n')
# Mark failed proxy replays as such; scalar-sufficient original replay remains exact.
f=P/'analysis/CAUSAL_ENDPOINT_REPLAY.json';d=json.loads(f.read_text());d['status']='REJECTED_TRACE_PROXY_REPLAY';d['source']='Archived trace cuff pose/twist fails original gap/rate reproduction; not established as guard-consumed Human interface';d['dual_result_scope']='OFFLINE_DIAGNOSTIC_ON_REJECTED_PROXY_ONLY';d['measured_axis_z_label']='TRACE_PROXY_AXIS_NOT_GUARD_INPUT';f.write_text(json.dumps(d,indent=2)+'\n')
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),hypothesis='原trace cuff pose可直接重放双端点因果输入',evidence='analysis/CAUSAL_ENDPOINT_REPLAY.json',result='gap误差0.0013007m、gap-rate误差0.015119m/s，原correction巧合相同不足以闭包',decision='拒绝该proxy重放；不以其轴偏差作机制结论。新物理只原guard并记录真实输入。预测器第一次导出遇list abs错误，修复后在未见候选START前冻结。',new_physics_from_errors=0),ensure_ascii=False)+'\n')
print('FACTORIAL_READY',len(cfg['actions']))
