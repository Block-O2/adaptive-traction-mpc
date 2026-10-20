from pathlib import Path
import hashlib,json,subprocess,ast,time
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/adaptive_continuous_coordination_optimization_v1');OLD=P.parent/'adaptive_continuous_coordination_interface_v1'
initial=json.loads((P/'audit/INITIAL_SOURCE_MANIFEST.json').read_text());changes=[];semantic=[]
for rel,expected in initial.items():
 f=P/rel
 if hashlib.sha256(f.read_bytes()).hexdigest()!=expected:
  old=(OLD/rel).read_text();new=f.read_text();path_only=old.replace(str(OLD),str(P))==new
  changes.append(dict(file=rel,path_rebase_only=path_only))
  if not path_only:semantic.append(rel)
allowed='source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/multisegment_reference.py'
assert semantic==[allowed],semantic
before=ast.parse((OLD/allowed).read_text());after=ast.parse((P/allowed).read_text());protected=['certify_path','current_path_check','geometry_path','seal_certificate','adapt_decision']
for n in protected:
 a=next(x for x in before.body if isinstance(x,ast.FunctionDef) and x.name==n);b=next(x for x in after.body if isinstance(x,ast.FunctionDef) and x.name==n);assert ast.dump(a)==ast.dump(b),n
git=Path('/home/hank/coding/adaptive-traction-mpc-learning');prior=json.loads((P/'audit/INITIAL_GIT_STATE.json').read_text());current={k:subprocess.check_output(['git','-C',str(git),*args],text=True) for k,args in [('branch',['branch','--show-current']),('HEAD',['rev-parse','HEAD']),('status',['status','--short'])]};assert current==prior,'PRODUCTION_GIT_STATE_CHANGED'
contract=(P/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes();assert contract==(OLD/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()
out=dict(status='PASS',unix=time.time(),compared_files=len(initial),changes=changes,semantic_changes=semantic,certificate_functions_AST_identical=protected,production_git_state_unchanged=True,motion_contract_byte_identical=True,scope='new copied closure versus original source; absolute path relocation is recorded separately from algorithm changes; original repository untouched',no_training=True,no_git_mutation=True)
(P/'PROTECTION_AUDIT.json').write_text(json.dumps(out,indent=2));print('PROTECTION_PASS',len(initial),len(changes),semantic)
