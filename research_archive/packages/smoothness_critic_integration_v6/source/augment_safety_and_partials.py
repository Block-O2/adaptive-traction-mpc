from pathlib import Path
import json,hashlib,csv
P=Path(__file__).resolve().parents[1];full=0;partial=0
for f in (P/'attempts').glob('*_RESULT.json'):
 r=json.loads(f.read_text());ident=r['id']
 if r['complete']:
  b=P/'analysis/branches'/(ident+'.json')
  if not b.exists():continue
  d=json.loads(b.read_text());m=json.loads((P/'runtime/reports'/(ident+'_MEASURED.json')).read_text());o=m['native_physical_audit']['unchanged_evaluator'];raw=o['raw_scorer_v2'];d['original_clearance_minima_m']={k:v for k,v in raw.items() if (k.startswith('minimum_') and 'clearance' in k) or k=='minimum_measured_sleeve_gap_m'};d['original_hard_safety_checks']=o['physical_task_result']['scorer_v2_common_conditions'];d['trace_torque_clipping_scope']='Original trace cadence measured5ms; exhaustive task clipping claim requires final receipt/component join audit';b.write_text(json.dumps(d,indent=2)+'\n');full+=1
 else:
  raw=P/'runtime/output'/(ident+'_DATA.json');data=json.loads(raw.read_text());metric=data['metric'];o=metric['physical_audit']['unchanged_evaluator'];out=dict(id=ident,complete=False,qualified=False,protected_task_failure=r.get('protected_task_failure'),actual_new_native_steps=r['actual_new_native_steps'],wall_s=r['wall_s'],partial_JF_unranked=metric.get('J_F'),partial_JM_unranked=metric.get('moment_integral'),original_scorer=o,raw_archive=str(P/'runtime/source/results'/ident/'runtime_artifacts.json.gz'),source_data_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),formal_full_task_cost_rank_allowed=False)
  target=P/'analysis/partials'/(ident+'.json');target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(out,indent=2)+'\n');partial+=1
print('SAFETY_AUGMENT',full,'PARTIALS',partial)
