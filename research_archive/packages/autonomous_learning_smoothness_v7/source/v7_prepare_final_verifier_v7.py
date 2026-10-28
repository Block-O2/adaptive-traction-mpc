"""Version a narrow failed-worker receipt audit. No science execution or old edits."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def put(rel, obj):
    with (P / rel).open('x') as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


base = P / 'source/v7_verify_final_package_v6.py'
dest = P / 'source/v7_verify_final_package_v7.py'
assert not dest.exists()
text = base.read_text()
helper = '''FAILED_JOIN_GROUP_IDS = {
 'DEVRT01':['DEVRT01_parent'],
 'DEVRT02':['DEVRT02_B','DEVRT02_parent'],
 'DEVRC01':['DEVRC01_B','DEVRC01_parent'],
 'HOLDSS02':['HOLDSS01_B','HOLDSS02_parent'],
}
def failed_worker_join_receipt_allowed(group, spec, worker, supervisor, attempts):
 """Accept only current closure evidence, never invent a normal original receipt."""
 if group not in FAILED_JOIN_GROUP_IDS:return False
 if spec.get('failed_join_receipt_schema')!='ihear.failed_worker_join_receipt.v1':return False
 if spec.get('normal_worker_join_receipt_missing_acknowledged') is not True:return False
 if worker.get('status')!='FAILED_PRESERVED' or 'all_children_joined' in worker:return False
 if supervisor.get('state')!='STOP' or supervisor.get('worker_exit_code')!=1 or supervisor.get('survivors')!=[]:return False
 if sorted(x.get('id','') for x in attempts)!=FAILED_JOIN_GROUP_IDS[group]:return False
 known={(q['pid'],q['start_ticks']) for q in identities(supervisor.get('known_owned',{}))}
 if not known:return False
 for a in attempts:
  s,e=a.get('START',{}),a.get('END',{})
  if a.get('group')!=group or s.get('group')!=group or e.get('joined') is not True:return False
  if s.get('id')!=a.get('id') or e.get('id')!=a.get('id'):return False
  if any(type(d.get(k)) is not int for d in (s,e) for k in ('pid','start_ticks')):return False
  if (s['pid'],s['start_ticks'])!=(e['pid'],e['start_ticks']) or (s['pid'],s['start_ticks']) not in known:return False
  if e.get('unix',0)<s.get('unix',0):return False
 return True

'''
text = text.replace('def identity():', helper + 'def identity():', 1)
old = "    if w.get('all_children_joined') is not True:self.issue('CHILDREN_NOT_JOINED',group=g)"
new = '''    if w.get('all_children_joined') is not True:
     spec=engineering.get(g,{})
     allowed=failed_worker_join_receipt_allowed(g,spec,w,s,groups[g])
     if allowed:
      before=len(self.issues)
      proof=self.reference(spec.get('failed_join_receipt_evidence'),'failed_worker_join_receipt:'+g)
      if proof is None:allowed=False
      for a in groups[g]:
       allowed=self.process_audit(a['START'],'failed_worker_START:'+a['id']) and allowed
       allowed=self.process_audit(a['END'],'failed_worker_END:'+a['id']) and allowed
      allowed=allowed and len(self.issues)==before
     if not allowed:self.issue('CHILDREN_NOT_JOINED',group=g)
     else:self.observations.setdefault('failed_worker_normal_join_receipt_missing',[]).append({'group':g,'original_WORKER_DONE_not_modified':True,'original_normal_join_certificate_present':False,'original_failure_preserved':True,'recorded_attempt_START_END_and_supervisor_processes_closed':True,'scope':'Declared PID/start_ticks only; not universal unrecorded-orphan proof'})'''
assert text.count(old) == 1
text = text.replace(old, new)
old_ast, new_ast = ast.parse(base.read_text()), ast.parse(text)
before = {n.name: ast.dump(n) for n in old_ast.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
after = {n.name: ast.dump(n) for n in new_ast.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
assert all(after[k] == v for k, v in before.items() if k != 'Verifier')
old_methods = {n.name: ast.dump(n) for n in next(n for n in old_ast.body if isinstance(n, ast.ClassDef)).body if isinstance(n, ast.FunctionDef)}
new_methods = {n.name: ast.dump(n) for n in next(n for n in new_ast.body if isinstance(n, ast.ClassDef)).body if isinstance(n, ast.FunctionDef)}
assert all(new_methods[k] == v for k, v in old_methods.items() if k != 'run')
namespace = {'__name__': 'pure_fixture_no_cli'}
exec(compile(text, '<verifier-v7-pure>', 'exec'), namespace)
allowed = namespace['failed_worker_join_receipt_allowed']
g = 'DEVRT01'
spec = {'failed_join_receipt_schema': 'ihear.failed_worker_join_receipt.v1', 'normal_worker_join_receipt_missing_acknowledged': True}
worker = {'status': 'FAILED_PRESERVED'}
supervisor = {'state': 'STOP', 'worker_exit_code': 1, 'survivors': [], 'known_owned': {'1': {'pid': 1, 'start_ticks': 2}}}
row = {'id': 'DEVRT01_parent', 'group': g, 'START': {'id': 'DEVRT01_parent', 'group': g, 'pid': 1, 'start_ticks': 2, 'unix': 1}, 'END': {'id': 'DEVRT01_parent', 'pid': 1, 'start_ticks': 2, 'unix': 2, 'joined': True}}
fixtures = []


def check(name, group=g, sp=None, w=None, sup=None, rows=None, expected=False):
    value = allowed(group, spec if sp is None else sp, worker if w is None else w, supervisor if sup is None else sup, [row] if rows is None else rows)
    assert value is expected, name
    fixtures.append({'name': name, 'status': 'PASS'})


check('exact_failed_receipt_scope', expected=True)
check('healthy_job_not_waived', group='DEVRT03')
check('unregistered_scope', sp={})
check('missing_acknowledgement', sp={'failed_join_receipt_schema': spec['failed_join_receipt_schema']})
check('healthy_worker', w={'status': 'PASS'})
check('explicit_negative_join_flag', w={'status': 'FAILED_PRESERVED', 'all_children_joined': False})
check('nonstop_supervisor', sup={**supervisor, 'state': 'RUNNING'})
check('survivor', sup={**supervisor, 'survivors': [1]})
check('unexpected_exit', sup={**supervisor, 'worker_exit_code': 0})
check('missing_attempt', rows=[])
check('duplicate_attempt', rows=[row, row])
bad = copy.deepcopy(row); bad['END']['joined'] = False
check('unjoined_attempt', rows=[bad])
bad = copy.deepcopy(row); bad['END']['start_ticks'] = 3
check('identity_mismatch', rows=[bad])
bad = copy.deepcopy(row); bad['START']['pid'] = '1'
check('noninteger_identity', rows=[bad])
bad = copy.deepcopy(row); bad['END']['unix'] = 0
check('end_before_start', rows=[bad])
check('unknown_owner', sup={**supervisor, 'known_owned': {}})
dest.write_text(text)
put('audit/FINAL_VERIFIER_V7_PURE_FIXTURES.json', {'status': 'PASS', 'fixtures': fixtures, 'base_sha256': sha(base), 'source_sha256': sha(dest), 'all_other_methods_AST_unchanged': True, 'new_env_model_fit_physics': 0})
limits = json.loads((P / 'audit/FINAL_METADATA_LIMITATIONS_V1.json').read_text())
limits.update(created_unix=time.time(), failed_worker_normal_join_receipt_missing_groups=['DEVRC01', 'DEVRT01', 'DEVRT02', 'HOLDSS02'], failed_worker_current_closure_scope='Exact original ledger START/END joined receipts plus STOP/exit1/no-survivor supervisor and current recorded PID/start_ticks closure, not original normal-worker join certificate or universal unrecorded orphan proof.')
put('audit/FINAL_METADATA_LIMITATIONS_V2.json', limits)
builder = (P / 'source/v7_prepare_final_evidence_index_v1.py').read_text()
for oldname, newname in [('FINAL_EVIDENCE_INDEX_V1','FINAL_EVIDENCE_INDEX_V2'),('STATIC_PACKAGE_MANIFEST_PRESEAL_V1','STATIC_PACKAGE_MANIFEST_PRESEAL_V2'),('FINAL_METADATA_LIMITATIONS_V1','FINAL_METADATA_LIMITATIONS_V2'),('ENGINEERING_JOB_CLOSEOUT_INDEX_V1','ENGINEERING_JOB_CLOSEOUT_INDEX_V2'),('FINAL_INDEX_BUILD_SUMMARY_V1','FINAL_INDEX_BUILD_SUMMARY_V2'),('v7_verify_final_package_v6.py','v7_verify_final_package_v7.py'),('audit/final_verification_v6_preseal_v1/','audit/final_verification_v7_preseal_v2/')]:
    builder = builder.replace(oldname, newname)
needle = "    ('CPU_AND_GENERALIZATION_LIMITS',"
addition = "    ('FAILED_WORKER_JOIN_RECEIPT_LIMITED', 'FAILED_WORKER_NORMAL_JOIN_RECEIPT_MISSING', '/failed_worker_normal_join_receipt_missing_groups', ['DEVRC01', 'DEVRT01', 'DEVRT02', 'HOLDSS02'],\n     'Four preserved FAILED_PRESERVED WORKER_DONE receipts lack the normal aggregate join flag. Exact original attempt joins, supervisor STOP/exit1/no survivors and current recorded PID closure are checked separately; no normal receipt reconstructed.'),\n"
assert builder.count(needle) == 1
builder = builder.replace(needle, addition + needle)
needle = "engineering['DEVRT02'].update("
addition = """for g in ['DEVRT01', 'DEVRT02', 'DEVRC01', 'HOLDSS02']:
    worker_path = 'jobs/' + g + '/WORKER_DONE.json'
    worker = read(worker_path)
    assert 'all_children_joined' not in worker and worker.get('status') == 'FAILED_PRESERVED'
    engineering[g].update(
        failed_join_receipt_schema='ihear.failed_worker_join_receipt.v1',
        normal_worker_join_receipt_missing_acknowledged=True,
        failed_join_receipt_evidence=ref(worker_path, {'/status': 'FAILED_PRESERVED', '/error': worker['error']}),
    )
"""
assert builder.count(needle) == 1
builder = builder.replace(needle, addition + needle)
with (P / 'source/v7_prepare_final_evidence_index_v2.py').open('x') as f:
    f.write(builder)
report = P / 'REPORT.md'
backup = P / 'audit/REPORT_BEFORE_FINAL_JOIN_RECEIPT_CLARIFICATION.md'
assert not backup.exists()
backup.write_bytes(report.read_bytes())
report_text = report.read_text()
oldline = '所有物理supervisor均STOP、worker已join、END无survivors；独立审计和有界Agent计算也有退出证据。'
newline = '所有物理supervisor均STOP、END无survivors，逐次attempt均有原START/END闭合回执；4个工程失败WORKER_DONE缺正常汇总join字段，保留为metadata限制，并另核对监督器退出、已记录PID/start_ticks及逐次join证据。独立审计和有界Agent计算也有退出证据。'
assert report_text.count(oldline) == 1
report.write_text(report_text.replace(oldline, newline))
registration = {'event': 'REGISTER_VERSIONED_FINAL_VERIFIER_FAILED_WORKER_JOIN_RECEIPT_LIMIT', 'unix': time.time(), 'id': 'FINAL_VERIFIER_V7_FAILED_WORKER_JOIN_RECEIPT', 'source': str(dest.relative_to(P)), 'source_sha256': sha(dest), 'base_v6_sha256': sha(base), 'hypothesis': 'Four actual failed-worker receipts lack normal aggregate join fields; original per-attempt joined START/END, stopped failed supervisors and independent current recorded-process closure support closure with a documented receipt limitation. No original normal join certificate can be claimed.', 'scope': sorted(namespace['FAILED_JOIN_GROUP_IDS']), 'fixtures': len(fixtures), 'budget': {'wall_s': 1200, 'threads': 1, 'new_env_model_fit_physics': 0, 'global_deadline_unix': 1793073411.846771}, 'output': 'audit/final_verification_v7_preseal_v2; FINAL_EVIDENCE_INDEX_V2; STATIC_PACKAGE_MANIFEST_PRESEAL_V2', 'stop': 'Narrow exact failed jobs only; live/zombie or bad attempt joins remain failures. Preserve all old failed verifier outputs, missing original receipts and engineering failures. No raw/source/scorer/physics verdict changes; no generic join waiver.'}
with (P / 'RESEARCH_DECISIONS.jsonl').open('a') as f:
    f.write(json.dumps(registration, ensure_ascii=False) + '\n')
print('PREPARED_V7', sha(dest), len(fixtures), 'pure fixtures; no actual final verification yet')
