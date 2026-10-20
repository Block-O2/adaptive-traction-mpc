"""C13: one decoded immutable original TASK graph for decision and proof prep.

Compile the exact original function bodies with their sole redundant decode
assignment replaced by a supplied original tuple. No controller/planner or
certificate arithmetic is edited. Advisory preparation still uses its separate
original snapshot after the packet is sent.
"""
import ast,copy,inspect,hashlib
EXECUTE=None;PREPARE=None;EVIDENCE=None
def clone(original,old_assignment,other_arguments):
 source=inspect.getsource(original);tree=ast.parse(source);fn=tree.body[0]
 assert isinstance(fn,ast.FunctionDef)
 expected=ast.dump(ast.parse(old_assignment).body[0])
 match=[i for i,s in enumerate(fn.body) if ast.dump(s)==expected]
 assert len(match)==1,(original.__name__,match)
 index=match[0];old_body=copy.deepcopy(fn.body)
 fn.name=original.__name__+'_decoded_once'
 fn.args.args=[ast.arg(arg='predecoded')]+[ast.arg(arg=x) for x in other_arguments]
 fn.body[index]=ast.parse(old_assignment.split(' = ')[0]+' = predecoded').body[0]
 # All other original statements, imports, math, branches and exceptions remain.
 assert all(ast.dump(a)==ast.dump(b) for i,(a,b) in enumerate(zip(old_body,fn.body)) if i!=index)
 ast.fix_missing_locations(tree);namespace=dict(original.__globals__)
 exec(compile(tree,'<original immutable TASK decode reuse>','exec'),namespace)
 return namespace[fn.name],dict(original_function=original.__module__+'.'+original.__name__,original_source_sha256=hashlib.sha256(source.encode()).hexdigest(),only_changed_statement=old_assignment,replacement='original tuple decoded once',all_other_AST_statements_identical=True)
def install():
 global EXECUTE,PREPARE,EVIDENCE
 if EXECUTE is not None:return
 from traction_mpc_stage5.full3d_adaptive_integration_v1 import online_planning as op
 import admission_certificates as cert
 EXECUTE,a=clone(op.execute_task_snapshot,'planner, arguments = pickle.loads(payload)',[])
 PREPARE,b=clone(cert.prepare,'planner, args = pickle.loads(payload)',['decision'])
 EVIDENCE=dict(version='C13',rows=[a,b],original_native_admission_unchanged=True,live_plant_received=False)
