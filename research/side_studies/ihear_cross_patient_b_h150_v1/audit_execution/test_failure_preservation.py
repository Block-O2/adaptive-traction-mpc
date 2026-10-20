"""Synthetic offline evidence tests. No simulation starts."""
from pathlib import Path
import importlib.util,json,tempfile,ast,sys
here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('failure_offline',here/'failure_receipt_audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
canonical=m.P
review=Path(m.read(canonical/'ENVIRONMENT.json')['review'])
def test(full_integral=None,qualified=False):
    with tempfile.TemporaryDirectory(prefix='ihear_offline_failure_fixture_') as folder:
        p=Path(folder);r=p/'review';r.mkdir();(p/'audit').mkdir();(p/'reports').mkdir()
        def put(name,v):
            q=p/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(v))
        put('ENVIRONMENT.json',dict(review=str(r)))
        put('audit/P99_OWNER.json',dict(joined=True))
        put('P99_DONE.json',dict(status='FAILED_PRESERVED',all_children_joined=True,cold_commissioning_reached=False,error='synthetic pre-fork failure'))
        put('P99_WORKER_EXIT.json',dict(active_child=None))
        (p/'ATTEMPTS.jsonl').write_text(json.dumps(dict(event='START',id='P99_parent'))+'\n'+json.dumps(dict(event='END',id='P99_parent',joined=True,error='synthetic pre-fork failure'))+'\n')
        put('reports/P99_parent_ERROR.json',dict(error='synthetic pre-fork failure'))
        put('reports/P99_parent_CROSS_EVALUATION.json',dict(complete_task=False,integration='NOT_EVALUABLE',J_F_N_s=full_integral,qualification='COMPLETE_QUALIFIED_PASS' if qualified else 'TASK_FAIL',absolute_task_execution_qualified=qualified))
        m.P=p;result=m.review('P99');m.P=canonical
        return dict(status=result['status'],checks=result['checks'],states=[x['state'] for x in result['rows']])
positive=test();bad_integral=test(0.0);bad_qualified=test(qualified=True)
assert positive['status']=='EVIDENCE_PRESERVATION_PASS'
assert positive['states']==['NOT_STARTED','NOT_STARTED','PARTIAL_OR_UNVERIFIED_PRESERVED']
assert bad_integral['status']=='EVIDENCE_PRESERVATION_FAIL'
assert bad_qualified['status']=='EVIDENCE_PRESERVATION_FAIL'
compiled=[]
for f in here.glob('*.py'):ast.parse(f.read_text());compiled.append(f.name)
result=dict(status='PASS',positive_prefork=positive,invalid_partial_zero_full_integral=bad_integral,invalid_partial_qualified_pass=bad_qualified,syntax_checked=compiled,new_physics_starts=0)
for root in [canonical,review]:
    f=root/'audit/OFFLINE_FAILURE_PRESERVATION_TEST.json';assert not f.exists();f.write_text(json.dumps(result,indent=2)+'\n')
assert not any(k in sys.modules for k in ['mujoco','study_common','cross_runner','sac_env'])
print(json.dumps(dict(status='PASS',cases=3,compiled=len(compiled),new_physics_starts=0)))
