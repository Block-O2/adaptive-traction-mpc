from pathlib import Path
import json,time,copy,shutil,hashlib
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
H=P.parent/'m2_18d_w1_d_qualification_v1';A=P.parent/'m2_18d_early_return_motion_repair_v1'
def read(p):return json.loads(p.read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
assert not (P/'Bmap_PLAN.json').exists()
old=read(H/'R0_PLAN.json');cond=copy.deepcopy(old['condition']);cond['name']='Bmap';cond['role']='already exposed R0 controlled background; fixed W1 OUTBOUND and no RETURN0 background; NOT unseen validation'
arms=copy.deepcopy(read(P/'Adev_PLAN.json')['arms'][:4])
put('Bmap_PLAN.json',dict(frozen_unix=time.time(),condition=cond,fork_after_prefix=1,arms=arms,reproduce_W1=False,historical_condition='R0',historical_reproduction_postcheck_required=['B','T','D'],classification='EXPOSED_STATE_DIAGNOSTIC',parent_ER_parameters_sha256=hashlib.sha256(json.dumps(arms[-1],sort_keys=True).encode()).hexdigest()))
protocol=dict(track='B',registered_unix=time.time(),hypothesis='The frozen Early RETURN composite that repairs W1 p95 but fails excursion may have different absolute and relative burdens when RETURN0 background is removed; slot-based timing repair need not transfer even within same Human',known='R0 is already exposed; W1/R0 share legal OUTBOUND history and use same seed; R0 B/T/D previously qualify',allowed_change='Background condition only. B/T/D and exact ER110_R4_120 rules remain fixed. No state-dependent policy or retuning.',comparison='Full B/T/D/ER from same live fork after true commissioning and legal OUTBOUND0. Postcheck B/T/D physical raw against archived R0. Compare absolute motion and own matched-B qualification separately.',success='Complete task/safety/receipt and all original motion gates for ER; all original gates mandatory. No broad promotion from one exposed background.',failure='Record original failed gates, rejected intentions, partials, and downstream cost. Do not tune on this condition.',budget=dict(total_START=5,includes_parent=True,all_serial=True),stop='Original task/safety/causal failure stops; no additional B candidate regardless of outcome',unseen_validation=False)
put('TRACK_B_PROTOCOL.json',protocol)
with (P/'MULTI_TRACK_DECISION_LOG.md').open('a') as f:f.write('\n## D2 — Track B额外受控背景诊断\n在A结果前登记R0/Bmap固定B/T/D/ER完整同父配对（5 START）。目的检验W1开发的Early RETURN时间规则是否在已暴露R0仍具相同运动效应。所有参数不变，不把R0当未见状态，不按结果重调。这一独立方向在A失败时仍继续。\n')
for n in ['Bmap_PLAN.json','TRACK_B_PROTOCOL.json','MULTI_TRACK_DECISION_LOG.md']:shutil.copy2(P/n,R/n)
print(json.dumps(dict(status='REGISTERED',condition=cond,arms=[x['id'] for x in arms],START_budget=5)),flush=True)
