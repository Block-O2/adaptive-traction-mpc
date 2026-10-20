from data_collection import BranchInterface
from study_common import *
from inference import Networks
class SynergyInterface(BranchInterface):
 def __init__(self,table,weights):
  super().__init__('heldout_known_synergy','test',table,5,[['OUTBOUND',3]]);self.weights=weights
 def make_plans(self,b,c,label):
  original=np.asarray(read('HISTORICAL_K2_SYNERGY_DESIGN_REFERENCE.json')['table']);future=[(0,j) for j in range(self.count['OUTBOUND'],5)]+[(1,j) for j in range(self.count['RETURN'],5)];plans=[];rows=[];network=Networks(self.weights)
  for index,length in enumerate((0,1,2,3,len(future))):
   plan=np.zeros((2,5,3))
   for phase,i in future[:length]:plan[phase,i]=original[phase,i]
   prediction=self.predictor.predict(b,c,plan,self.count);delta=network.value(prediction['terminal']['feature']);plans.append(plan);rows.append(dict(index=index,prefix_length=length,label='FULL' if index==4 else 'L'+str(length),P_score=prediction['total_cost'],PV_score=prediction['total_cost']+delta,deltaV=delta,prediction=prediction,plan=plan))
  save('KNOWN_NONMYOPIC_POOL.json',dict(label=label,rows=rows,weights=self.weights,split='test',new_physical_labels_only=True,continuation='native-certified-committed-K3-suffix-v1',semantics='historically discovered K2 family represented exactly in K3; first L native coordinated actions then B, or coherent full remaining suffix; no online physical scoring'))
  return plans
