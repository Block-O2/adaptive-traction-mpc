from pathlib import Path
import json,copy,hashlib,datetime
P=Path(__file__).resolve().parents[1];fact=json.loads((P/'experiments/FACT.json').read_text());c=copy.deepcopy(fact);c.update(group='VAL_C',mode='validation',historical_repeats={},actions=[],worker='v4_factor_worker.py',job_wall_cap_s=2400);c['condition']=dict(name='VAL_C',seed=2026102213,prefix={'OUTBOUND':[[.075,.045,.02]],'RETURN':[[.035,.015,.03]]},split='locked_post_development_validation',role='new prefix never used in candidate selection',Human='same nominal commissioned Human; actual legal prefix')
by={a['tag']:a for a in fact['actions']}
for old,new in [('B','B'),('BEST_L1_D1','BEST_CONTROL'),('BEST_L1_D0','BEST_OLD_DURATION')]:
 a=copy.deepcopy(by[old]);a.update(tag=new,category='locked_factor_candidate_validation');c['actions'].append(a)
for n in ['experiments/VAL_C.json','runtime/VAL_C_TEST_PLAN.json']:(P/n).write_text(json.dumps(c,indent=2)+'\n')
out=dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reason='Developed L1D0 qualifies and reduces JF with JM cost; requires independent check before robustness claims',source_development_result_sha256=hashlib.sha256((P/'attempts/FACT_BEST_L1_D0_RESULT.json').read_bytes()).hexdigest(),config_sha256=hashlib.sha256((P/'experiments/VAL_C.json').read_bytes()).hexdigest(),condition=c['condition'],actions=c['actions'],budget=dict(additional_physics_cap=4,additional_native_cap=600000,job_wall_cap_s=2400),no_candidate_changes_after_validation=True,guard='UNCHANGED_ORIGINAL',comparison='endpoint lock fixed true; only duration compiler changes within each matched live parent')
(P/'analysis/LOCKED_FACTOR_VALIDATION_FREEZE.json').write_text(json.dumps(out,indent=2)+'\n')
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps(dict(utc=out['frozen_utc'],hypothesis='保留终点锁但恢复旧时长编译可在同任务下降力，JM可能增加；需新prefix确认',evidence='attempts/FACT_BEST_L1_D0_RESULT.json',result={'JF':1397.3837971707242,'JM':108.63914279549681,'original_motion':'PASS'},decision='追加唯一冻结VAL_C，在新合法prefix同父配对原BEST与L1D0；不改已有VAL_A/B，不做Learning归因',budget=out['budget']),ensure_ascii=False)+'\n')
print('FROZEN_VAL_C',out['config_sha256'])
