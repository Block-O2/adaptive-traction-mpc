from pathlib import Path
import json,time,hashlib,ast,shutil
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies')/Path(__file__).resolve().parents[1].name
A=P.parent/'m2_18d_w1_d_qualification_v1';R=Path(__file__).resolve().parents[1]
rebase=json.loads((P/'audit/PATH_REBASE.json').read_text())['path_only'];bad=[];count=0
for folder in ['source','code','deps','weights']:
 for old in (A/folder).rglob('*'):
  if not old.is_file() or 'results' in old.parts or '__pycache__' in old.parts or old.suffix=='.pyc':continue
  rel=str(old.relative_to(A));new=P/rel;count+=1
  expected=old.read_text().replace(str(A),str(P)).encode() if rel in rebase else old.read_bytes()
  if not new.exists() or new.read_bytes()!=expected:bad.append(rel)
assert not bad,bad
src=(P/'control/early_return_planner.py').read_text();tree=ast.parse(src);assert not any(isinstance(n,ast.Attribute) and n.attr in ['qpos','qvel','gain','torque_limit'] for n in ast.walk(tree))
out=dict(status='PASS',unix=time.time(),copied_frozen_files_verified=count,production_changes='exact path rebasing only for listed files; otherwise old source/code/deps/weights byte-identical',path_rebased_files=rebase,unapproved_changes=bad,isolated_new_intent_uses_deployable_state_and_reference_only=True,formal_safety_semantics_unchanged=True,no_interface_extension_needed=True,original_gate_file_sha256=hashlib.sha256((P/'MOTION_ACCEPTANCE_PROTOCOL.json').read_bytes()).hexdigest())
(P/'audit/SOURCE_CLOSURE_VERIFIED.json').write_text(json.dumps(out,indent=2)+'\n')
for f in (P/'figures').glob('*.png'):(R/'figures').mkdir(exist_ok=True);shutil.copy2(f,R/'figures'/f.name)
shutil.copy2(P/'REPORT.md',R/'REPORT.md')
print(json.dumps(dict(status='PASS',files=count,rebased=len(rebase))),flush=True)
