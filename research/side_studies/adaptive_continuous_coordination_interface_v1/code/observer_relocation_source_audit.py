from task_bootstrap import *
import ast
def main():
 root=STUDY/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/full3d_adaptive_integration_v1';rows=[];unexpected=[]
 for name in ('runtime_coordination_residual_v2.py','runtime_sac_expert_v1.py','wall_physics.py'):
  path=root/name;text=path.read_text();tree=ast.parse(text);parents={child:node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)};uses=[]
  for node in ast.walk(tree):
   if not isinstance(node,ast.Subscript) or not isinstance(node.slice,ast.Constant) or node.slice.value!='true_physics_monitor':continue
   parent=parents.get(node);attribute=parent.attr if isinstance(parent,ast.Attribute) else None;use=dict(line=node.lineno,attribute=attribute,assignment=isinstance(node.ctx,ast.Store),source=text.splitlines()[node.lineno-1].strip());uses.append(use)
   if not(use['assignment'] or attribute in ('stage','observe','record')):unexpected.append(dict(file=name,**use))
  rows.append(dict(path=str(path),sha256=sha(path),uses=uses))
 assert not unexpected,'UNEXPECTED_OBSERVER_CONTROL_CONSUMER'
 contract=STUDY/'source/stages/stage5_personalized_motion_learning/src/traction_mpc_stage5/fresh_qualification_v1/physics_monitor.py'
 assert 'never used by estimation, waypoint planning, or safety control' in contract.read_text()
 out=dict(status='PASS',rows=rows,unexpected=unexpected,original_evaluation_only_declaration=str(contract),original_declaration_sha256=sha(contract),observer_inputs='Original current post-refresh shank/bed pose scalars, actual human q, cached current human wrench, actual shank/bed contact predicate, stage/native-boundary ownership; copied immediately at original node.',static_cache_scope='One plant/model identity, immutable model geometry sizes and Human ROM bounds; validated unchanged at aggregation. No state, reference, belief or ownership certificate reuse added.',original_formula_used_at_aggregation=True,controller_or_safety_consumer_removed=False,new_public_B_scheduling_repairs=0,physics_added=0,scope_limit='Static direct-key consumer audit plus original source declaration, validated further by complete SCI physical and evaluator-record equivalence. No broad claim about arbitrary third-party code.')
 save(STUDY/'reports/OBSERVER_RELOCATION_SOURCE_AUDIT.json',out);print(json.dumps(dict(status=out['status'],files=len(rows),uses=sum(len(r['uses']) for r in rows),unexpected=unexpected)))
if __name__=='__main__':main()
