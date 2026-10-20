"""Development-only same-state fixed-candidate ranking and full-consequence audit."""
from freeze import *
import sys,collections,numpy as np
sys.path.insert(0,str(STUDY/'code'))
from inference import Networks
def mask_feature(x,counts):
 x=np.asarray(x,np.float32).copy();table=x[58:88].reshape(2,5,3)
 for i,phase in enumerate(('OUTBOUND','RETURN')):table[i,:counts[phase]]=0.
 return x
def main():
 version=int(sys.argv[1]);weights=json.loads((STUDY/'LATEST_WEIGHTS.json').read_text());assert weights['version']==version;network=Networks(weights['weights']);groups=collections.defaultdict(list)
 for p in (STUDY/'output').glob('*_DATA.json'):
  r=json.loads(p.read_text())
  if r.get('split')!='dev' or not r['metric']['valid']:continue
  first=next((q for q in r['value_rows'] if 'model_prediction' in q),None)
  if first is None:continue
  pred=first['model_prediction'];x=mask_feature(pred['terminal']['feature'],pred['terminal']['count'])
  phase=pred['terminal']['phase'];counts=pred['terminal']['count'];index=counts[phase]-1
  previous=np.asarray(r['table'])[('OUTBOUND','RETURN').index(phase),index] if counts[phase]>first['count'][phase] and index<5 else np.zeros(3) if counts[phase]>first['count'][phase] else np.asarray(first['context'].get('richer_previous_residual',[0,0,0]))
  from study_common import sac_env
  raw=np.zeros(55);raw[49:51]=previous[[0,2]];x[49:51]=sac_env.normalized(raw)[49:51];x[55:58]=previous
  P=pred['total_cost'];PV=P+network.value(x)
  groups[r['child']['label']].append(dict(id=r['id'],physical_remaining_J_F=r['remaining_J_F'],P_score=P,PV_score=PV,table=r['table'],source='same-state branch actual full consequence; frozen committed suffix'))
 diagnostics=[]
 for group,rows in groups.items():
  truth=min(rows,key=lambda r:r['physical_remaining_J_F']);base=next((r for r in rows if r['id'].endswith('candidate0')),None);p=min(rows,key=lambda r:r['P_score']);pv=min(rows,key=lambda r:r['PV_score'])
  diagnostics.append(dict(group=group,rows=rows,best_reference=truth['id'],best_J_F=truth['physical_remaining_J_F'],baseline_J_F=None if base is None else base['physical_remaining_J_F'],P_selected=p['id'],P_regret_Ns=p['physical_remaining_J_F']-truth['physical_remaining_J_F'],PV_selected=pv['id'],PV_regret_Ns=pv['physical_remaining_J_F']-truth['physical_remaining_J_F'],good_route_present=base is not None and truth['physical_remaining_J_F']<base['physical_remaining_J_F']*.995))
 record=dict(version=version,data_split='development only',diagnostics=diagnostics,candidate_pool_fixed=True,same_random_numbers=True,actual_physics_labels=True,online_extra_physics=False,test_used=False,legacy_feature_repair='past table masked and last actually applied K3 history retained through B-owned endpoint, using unchanged normalization; old input files/costs preserved',full_consequence_reference='8 candidates in bounded two-stage multi-start physical search at each reserved dev snapshot; no global optimum claim',next_predeclared_coverage='Add exactly one legal parent from qualified P executed table, else half historical K3 design table; same pi_cont and no held-out labels',model_or_policy_changes=0)
 save(STUDY/f'DEVELOPMENT_DIAGNOSIS_v{version}.json',record);print(json.dumps(dict(version=version,groups=len(diagnostics),good_route_groups=sum(r['good_route_present'] for r in diagnostics),P_regret_Ns=[r['P_regret_Ns'] for r in diagnostics],PV_regret_Ns=[r['PV_regret_Ns'] for r in diagnostics])))
if __name__=='__main__':main()
