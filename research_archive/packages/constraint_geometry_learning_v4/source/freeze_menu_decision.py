from pathlib import Path
import os,sys,json,numpy as np
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'source'));from acl2_shared import put,sha,utc,append
O=P.parent/'representation_execution_v3';training=[]
for tag,delta in [('C19_DM0p0010',-.001),('C19_DP0p0010',.001)]:
 f=O/'attempts'/('P2_'+tag+'_RESULT.json');r=json.loads(f.read_text());assert r['qualified'];training.append(dict(delta=delta,JF=r['JF'],JM=r['JM'],source_sha256=sha(f)))
X=np.array([[1.,r['delta']] for r in training]);c=np.linalg.solve(X,np.array([r['JF'] for r in training]));cM=np.linalg.solve(X,np.array([r['JM'] for r in training]));pred=json.loads((P/'predictions/DEV_PREREGISTERED_PREDICTIONS.json').read_text());menu=[]
for a in pred['actions']:
 if 'local_delta' not in a:continue
 d=a['local_delta'];pr=a['prediction'];menu.append(dict(tag=a['tag'],delta=d,predicted_JF=float(np.array([1.,d])@c),predicted_JM=float(np.array([1.,d])@cM),branch_predicted_motion_pass=pr['predicted_motion_pass']))
direct=min(menu,key=lambda r:r['predicted_JF']);aware=min((r for r in menu if r['branch_predicted_motion_pass']),key=lambda r:r['predicted_JF']);out=dict(status='POSTHOC_RULE_DIAGNOSTIC_NOT_PROSPECTIVE_OPTIMIZER',created_utc=utc(),training=training,force_cost_coefficients=c.tolist(),moment_cost_coefficients=cM.tolist(),menu=menu,cost_only_selection=direct,branch_aware_selection=aware,selection_changed=direct['tag']!=aware['tag'],physics_budget_note='Both rules use identical historical information and one common frozen 6-action physics menu. This is a decision/ranking diagnostic, not two independent optimization arms; no duplicated physical budget or optimizer efficiency claim.',next_action='No independent learning training or duplicate 2x8 optimizer run: both explicit methods select same action, so those repetitions do not isolate an incremental decision benefit.')
put('predictions/FROZEN_MENU_DECISION.json',out);append('RESEARCH_DECISIONS.jsonl',dict(utc=utc(),hypothesis='显式分支信息是否在局部低force菜单改变传统成本选择',evidence='predictions/FROZEN_MENU_DECISION.json',result='同历史数据的两规则均选LOCAL_M0p0008，预先未改变决策',decision='仍执行所有冻结未见菜单检验资格预测；不重复两臂相同物理来制造效率比赛。P3-B新旧guard优化NOT_RUN。',learning='NO_TRAINING_WITHOUT_IDENTIFIED_INCREMENTAL_DECISION_VALUE'))
print('SELECTIONS',direct['tag'],aware['tag'],'changed',out['selection_changed'])
