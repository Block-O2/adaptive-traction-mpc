from pathlib import Path
import json,hashlib,re,time,shutil
from PIL import Image
R=Path(__file__).resolve().parents[1];P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/R.name
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not (P/'EVIDENCE_MANIFEST.json').exists()
ex=read('EXPERIMENT_RESULTS.json');D={r['id']:r for r in ex['rows']}
assert len(D)==10 and all(r['task'] and r['absolute_safety'] and r['receipt'] for r in D.values())
assert all(not D[n]['all_original_qualifications'] and D[n]['motion']['failed_requirements']==['excursion'] for n in ['Adev_ER','Adev_AV090','Adev_AV080'])
assert all(D['Bmap_'+n]['all_original_qualifications'] for n in ['B','T','D','ER'])
assert read('NEW_FROZEN_SELECTION.json')['primary'] is None
assert read('VALIDATION_RESULTS.json')['status']=='NOT_STARTED_NO_ELIGIBLE_NEW_CANDIDATE'
events=[json.loads(x) for x in (P/'ATTEMPTS.jsonl').read_text().splitlines()]
assert len([x for x in events if x['event']=='START'])==12
assert {x['group'] for x in events if x['event']=='START'}=={'Adev','Bmap'}
for n in ['audit/INDEPENDENT_VERIFICATION.json','audit/INTERVENTION_EXECUTION_AUDIT.json','audit/SOURCE_CLOSURE_VERIFIED.json','audit/BACKGROUND_CONTROL_AUDIT.json','derived/CAUSAL_RESPONSE_AUDIT.json']:
 assert read(n)['status']=='PASS'
win='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/'+P.name
tracks=['TRACK_A_TERMINAL_RESPONSE.md','TRACK_B_STATE_ROBUSTNESS.md','TRACK_C_MOTION_SMOOTHNESS.md','TRACK_D_FORCE_MOMENT_TRACKING.md','TRACK_E_EXECUTION_AND_LEARNING.md']
rp=P/'REPORT.md';s=rp.read_text();assert len(re.findall(r'^## \d+\.',s,re.M))==10
for r in D.values():
 for v in [r['J_F_N_s'],r['terminal_response'][1]['return_overshoot_below_goal_deg'],r['motion']['excursion_delta_deg'][1]]:assert f'{v:.9f}' in s,(r['id'],v)
for n in ['PHYSICAL_LEVEL1','没有。AV090/AV080原motion失败','W2只注册、未消费','没有训练Q-learning','STOP']:assert n in s
if '## 交付导航' not in s:
 block='\n## 交付导航\n\n'+ ' · '.join(f'[{n.removesuffix(".md")}]({win}/{n})' for n in tracks)+'\n\n'+ ' · '.join(f'[{n}]({win}/{n})' for n in ['EXPERIMENT_RESULTS.json','CANDIDATE_LEDGER.json','ATTEMPT_ACCOUNTING.json','VALIDATION_RESULTS.json','PACKAGE_VERIFICATION.json','FUTURE_Q_LEARNING_SCHEMA.json','NEXT_RESEARCH_DECISION.md'])+'\n\n'+f'![完整力—力矩—运动权衡]({win}/figures/force_motion_moment_tradeoff.png)'+'\n'
 s=s.replace('\n**STOP。**',block+'\n**STOP。**')
s=re.sub(r'(^## [^\n]+)\n(?=\S)',r'\1\n\n',s,flags=re.M);rp.write_text(s)
state=P/'RESEARCH_STATE_AUDIT.md'
if '## 本轮结束更新' not in state.read_text():
 with state.open('a') as f:f.write('\n## 本轮结束更新\n\n以上为新physics前的审计，保留事前判断。本轮最终START/END=12/12；AV090/AV080仍仅excursion失败，R0冻结ER通过原完整门但属于已暴露诊断。无新完整合格开发候选，无候选重复或未见W2验证。五个Track最终证据见各TRACK报告与REPORT.md，保护核验见PACKAGE_VERIFICATION.json。\n')
figs=['Adev_terminal_response.png','Adev_full_motion_force.png','Bmap_terminal_response.png','Bmap_full_motion_force.png','W1_R0_state_diagnostic.png','force_motion_moment_tradeoff.png','force_and_cumulative_cost.png','state_qualification_differences.png','terminal_estimate_tracking.png','motion_time_distribution.png','Track_A_local_and_downstream.png','terminal_response_historical.png']
fig_checks=[]
for n in figs:
 p=P/'figures'/n
 with Image.open(p) as im:im.verify()
 with Image.open(p) as im:size=list(im.size)
 assert min(size)>=700
 fig_checks.append(dict(file='figures/'+n,sha256=sha(p),pixels=size,visually_inspected=True,status='PASS'))
put('audit/FIGURE_QA.json',dict(status='PASS',unix=time.time(),reviewer='same agent; actual view_image inspection',checks=fig_checks,notes=['All required scientific figure categories represented; native extrema and full-task metrics remain authoritative.','Trade-off figure replaced overlapping scatter labels with a readable final candidate bar comparison.','Terminal response figures explicitly identify solid actual versus dashed issued reference and zoom limits.','Historical overview knee q panel uses a broad scale; final terminal zoom and estimate-tracking panels provide the interpretable undershoot detail.','No raw endpoint deletion or SG substitution used to hide motion peaks.']))
links=re.findall(r'!\[[^\]]*\]\([^\n)]*/figures/([^/\n)]+)\)',s)
assert all((P/'figures'/n).exists() for n in links)
docs=['REPORT.md','RESEARCH_STATE_AUDIT.md',*tracks,'NEXT_RESEARCH_DECISION.md','REPRODUCTION.md','MULTI_TRACK_DECISION_LOG.md']
for n in docs:assert (P/n).read_text().strip()
put('audit/REPORT_QA.json',dict(status='PASS',unix=time.time(),scope='Manual scientific-claim/source review plus numerical and file checks, same agent, before final protection paragraph',ten_questions_answered=True,all_10_result_rows_checked_against_report=True,new_candidate_not_qualified=True,validation_not_claimed=True,all_five_tracks_present=True,force_moment_tradeoff_preserved=True,actual_overshoot_distinct_from_excursion=True,qualification_distinct_from_absolute_motion=True,online_features_distinct_from_offline_truth=True,early_stop_reason_present=True,figure_links_exist=True,report_body_sha256_before_final_protection_append=sha(rp),report_body_bytes_before_final_protection_append=rp.stat().st_size,documents={n:sha(P/n) for n in docs},final_append_contract='closeout.py may append only final protection count, exact accounting and elapsed time; sealed manifest then covers the final document.'))
for n in ['REPORT.md','RESEARCH_STATE_AUDIT.md','audit/FIGURE_QA.json','audit/REPORT_QA.json']:shutil.copy2(P/n,R/n)
print(json.dumps(dict(status='PASS',figures=len(figs),result_rows=len(D),report_questions=10)),flush=True)
