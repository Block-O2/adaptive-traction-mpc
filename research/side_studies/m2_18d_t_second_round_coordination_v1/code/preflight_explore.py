from explore_common import *
import shutil,ast
def main():
 assert not (S/'ATTEMPTS.jsonl').exists(),'PROTOCOL_IMMUTABLE_AFTER_PHYSICS'
 win=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1')
 for p in win.glob('*.py'):
  if p.name!='bootstrap.py':shutil.copy2(p,S/'code'/p.name)
 for p in (S/'code').glob('*.py'):ast.parse(p.read_text(),filename=str(p))
 proto=load(S/'EXPERIMENT_PROTOCOL.json');proto['selection_materially_lower_burden_definition']='At least5% lower than same-seed frozen M2 for all three knee metrics: p95 speed, p95 acceleration, RMS acceleration; original primary acceptance and >=0.5% J_F gain over B required. Or J_F lower than M2 while meeting those primary gates.';proto['selection_rule_clarified_before_physics_unix']=time.time();save(S/'EXPERIMENT_PROTOCOL.json',proto)
 save(S/'CODE_MANIFEST.json',{str(p.relative_to(S)):sha(p) for d in ['code','deps','native','build','weights','source/stages'] for p in (S/d).rglob('*') if p.is_file()})
 from audit_space import main as audit
 audit()
 native=(S/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1/coordination_residual_v2.py');old=S.parent/'m2_host_generalization_attribution_v1'/native.relative_to(S)
 assert native.read_text()==old.read_text(),'NATIVE_B_SOURCE_CHANGED'
 assert sha(S/'weights/frozen_Q_v1/weights.npz')=='3be0536a8cd9007e8926fc1f49d97468facd2d09233bd89618d04e683b6d3db9'
 save(S/'PREFLIGHT.json',dict(status='PASS',unix=time.time(),all_code_parses=True,native_residual_source_unchanged=True,Q_identity=True,physics_attempts=0))
 print('PREFLIGHT_PASS',flush=True)
if __name__=='__main__':main()
