from freeze import *
import numpy as np
def main():
 origin=LOCAL.parent/'expert_strength_value_adequacy_v1/output/PREFIX_SOURCE_EXECUTION_MASK.json';mask=json.loads(origin.read_text());table=np.zeros((2,5,3));errors=[]
 for row in mask['rows']:
  phase=row['phase'];index=row['index'];points=np.asarray(row['graph'][phase]);start=points[1,0] if len(points)==5 else 0.
  knots=points[-3:-1,1]/.2;target=np.r_[knots[0],knots.mean(),knots[1]] if row['actually_activated'] else np.zeros(3)
  table[('OUTBOUND','RETURN').index(phase),index]=target
  if row['actually_activated']:
   new=np.array([[0.,0.],[start,0.],*[[(start+(1-start)*f),value*.2] for f,value in zip((.1,.4,.7),target)],[1.,0.]])
   grid=np.linspace(0,1,1001);errors.append(float(np.max(np.abs(np.interp(grid,points[:,0],points[:,1])-np.interp(grid,new[:,0],new[:,1])))))
 assert max(errors)<1e-12 and np.max(np.abs(table))<=1.;reference=dict(table=table.tolist(),source=str(origin),source_sha256=sha(origin),design_only=True,historical_labels_not_used=True,conversion='K2 [.1,.7] -> K3 [.1,.4,.7] by inserting exact linear midpoint; rejected historical graphs map to B',graph_grid_max_error=max(errors),target='historically known OUTBOUND native index3 nonmyopic prefix family; all costs newly measured')
 path=STUDY/'output/HISTORICAL_K2_SYNERGY_DESIGN_REFERENCE.json';assert not path.exists();save(path,reference)
 contract=json.loads((STUDY/'COMPARISON_v2_final.json').read_text());weights=contract['weights'];name='085_known_nonmyopic_synergy';save(STUDY/'queue'/(name+'.json'),dict(id=name,kind='physics',mode='synergy',group='heldout_known_synergy',split='test',weights=weights,table=table.tolist(),seed=2026100810,result_path=str(STUDY/'output'/(name+'_RESULT.json')),design_reference_sha256=sha(path),physical_attempt_budget=6));print(name)
if __name__=='__main__':main()
