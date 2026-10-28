"""SYNTHETIC ONLY: exercise actual inherited-generator close with Linux fork.

Uses exception-handler AST from both real sampling sources, with stub writers.
No policy/environment imports, model calls, fitting or simulated physics.
"""
from pathlib import Path
import ast,copy,gc,hashlib,json,os,time
P=Path(__file__).resolve().parents[1]
O=P/'audit/GENERATOR_FORK_CLEANUP_FIXTURE_V1';O.mkdir(exist_ok=False)
results=[]
for version in [1,2]:
    source=P/('families/ppo_reward/onpolicy_sequence_v'+str(version)+'.py')
    tree=ast.parse(source.read_text());sequence=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sequence')
    outer=next(n for n in sequence.body if isinstance(n,ast.Try));handler=copy.deepcopy(outer.handlers[0])
    # Test exactly the source's exception suite. Stub writes carry producer PID.
    function=ast.FunctionDef(name='probe',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[ast.Try(body=[ast.Expr(value=ast.Yield(value=ast.Constant(value='STUB_ONLY_NO_POLICY')))],handlers=[handler],orelse=[],finalbody=[])],decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    writes=O/('V'+str(version)+'_WRITES.jsonl');parent_pid=os.getpid()
    def append(kind,payload):
        with writes.open('a') as stream:stream.write(json.dumps({'producer_pid':os.getpid(),'kind':kind,'payload':payload})+'\n')
    namespace={'os':os,'time':time,'sequence_owner_pid':parent_pid,'output_relative':'SYNTHETIC_ONLY','save':lambda stage:append('save',stage),'put':lambda path,value:append('put',{'path':path,**value})}
    exec(compile(module,'<real-source exception handler only>','exec'),namespace)
    generator=namespace['probe']();next(generator)
    child=os.fork()
    if child==0:
        generator.close();os._exit(0)
    _,status=os.waitpid(child,0);assert os.waitstatus_to_exitcode(status)==0
    before_parent_close=[json.loads(line) for line in writes.read_text().splitlines()] if writes.exists() else []
    child_writes=[row for row in before_parent_close if row['producer_pid']==child]
    assert len(child_writes)==(2 if version==1 else 0),'INHERITED_GENERATOR_OWNER_GUARD_FAILURE'
    generator.close()  # Parent-owned cancellation remains visible and legitimate.
    after=[json.loads(line) for line in writes.read_text().splitlines()] if writes.exists() else []
    assert sum(row['producer_pid']==parent_pid for row in after)==2
    results.append({'source':str(source.relative_to(P)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'parent_pid':parent_pid,'real_test_child_pid':child,'child_exitcode':0,'child_cleanup_writes':len(child_writes),'parent_cleanup_writes':2,'physics':0,'real_model_initialization':0,'model_forward':0,'gradient_updates':0})
output={'status':'PASS_SYNTHETIC_LINUX_FORK_GENERATOR_CLOSE','rows':results,'source_scope':'Exact exception handler AST; no claim the entire sampling API or physics was reproduced','real_OS_test_forks':2,'real_physics_forks':0,'unix':time.time()}
(O/'RESULT.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))
