from freeze import *
import numpy as np,sys
def main():
 selection=sys.argv[1] if len(sys.argv)>1 else 'initial'
 groups=[('train_0','train',np.zeros((2,5,3))),('dev_0','dev',np.zeros((2,5,3)))] if selection=='initial' else [('train_1','train',np.asarray(json.loads((STUDY/'output/HISTORICAL_K3_DESIGN_REFERENCE.json').read_text())['table'])*.5)]
 if selection=='extension':
  qualified=STUDY/'output/012_P_completion_allowance_regression_RESULT.json'
  if qualified.exists() and json.loads(qualified.read_text()).get('metric',{}).get('valid'):
   table=np.zeros((2,5,3));decisions=json.loads((STUDY/'output/012_P_completion_allowance_regression_DECISIONS.json').read_text())['rows']
   for row in decisions:
    i=row['native_index']
    if i<5:table[('OUTBOUND','RETURN').index(row['phase']),i]=row['action']
   groups=[('train_1','train',table)]
 for i,(group,split,table) in enumerate(groups):
  if group=='dev_0':table[0,0]=[.04,.02,-.02]
  name=('010_' if group=='train_0' else '011_' if group=='dev_0' else '020_')+'parent_'+group
  p=STUDY/'queue'/(name+'.json');assert not p.exists()
  save(p,dict(id=name,kind='physics',mode='branches',group='parent_'+group,split=split,table=table.tolist(),candidates=8,result_path=str(STUDY/'output'/(name+'_RESULT.json')),targets=[['OUTBOUND',0],['OUTBOUND',2],['OUTBOUND',4],['RETURN',1]],source_role='legal state coverage from qualified P preflight trajectory when available; else preregistered half-K3 design reference',no_test_data=True))
 print(selection)
if __name__=='__main__':main()
