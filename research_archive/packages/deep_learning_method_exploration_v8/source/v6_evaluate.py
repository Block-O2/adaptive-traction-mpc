from pathlib import Path
import json,time,hashlib,sys,copy,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1');import numpy as np
from v6_selection import select
from v6_model import predict_cost
from v6_data import group as collect
P=Path(__file__).resolve().parents[1]
def put(n,x):f=P/n;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def physical_hash(ident):
 h=hashlib.sha256()
 with np.load(P/'runtime/source/results'/ident/'trace.npz') as z:
  for key in ['time_s','evaluation_only_human_state_rad_rad_s','reference_q_rad','reference_dq_rad_s','applied_generalized_action_nm']:h.update(z[key].tobytes())
 return h.hexdigest()
def evaluate(g,model_path,legacy=False):
 rows=collect(g,wrench=True);cfg=json.loads((P/'experiments'/f'{g}.json').read_text());frozen=json.loads((P/model_path).read_text());bundle=frozen['phases'][cfg['fork_phase']]
 source_seal=frozen.get('source_sha256',{})
 for rel,h in (source_seal.items() if isinstance(source_seal,dict) else []):assert hashlib.sha256((P/rel).read_bytes()).hexdigest()==h,'FROZEN_SOURCE_CHANGED:'+rel
 menu=[a['tag'] for a in cfg['actions']] if legacy else json.loads((P/'freeze/PRIMARY_MENU.json').read_text())['primary_menu'];half=[r for r in rows if r['horizon_s']==.5 and r['tag'] in menu];one=[r for r in rows if r['horizon_s']==1. and r['tag'] in menu];assert len(half)==len(menu),'INCOMPLETE_FROZEN_MENU'
 inp=[dict(tag=r['tag'],feature_names=r['feature_names'],features=r['features'],local_risk_features=r['local_risk_features'],history_risk_features=r['history_risk_features'],short_JF=r['labels']['short_JF']) for r in half];d=select(bundle,inp);fixed=bundle.get('fixed_training_policy_tag','RELATIVEP');valid=[r for r in half if r['qualified']];assert valid,'NO_QUALIFIED_OFFLINE_REFERENCE'
 choices={'A_FIXED_SMOOTH':'COMPOSE' if not legacy else fixed,'B_HALF_SECOND':min(half,key=lambda r:r['labels']['short_JF'])['tag'],'C_ONE_SECOND':min(one,key=lambda r:r['labels']['short_JF'])['tag'],'D_CRITIC':d['choice'],'E_REAL_FULL_REFERENCE':min(valid,key=lambda r:r['labels']['full_remaining_JF'])['tag'],'FIXED_TRAINING_CHOICE':fixed,'CRITIC_COST_ONLY':d['unrestricted_cost_choice']}
 if not legacy:
  choices.update(A_FIXED_HANDOFF='HANDOFF',A_FIXED_PATTERN='PATTERN',A_FIXED_BLEND='BLEND')
 guard_index=__import__('v6_observed_history').NAMES.index('past_guard_unsatisfied')
 guard_half=[r for r in half if r['history_risk_features'][guard_index]==0]
 guard_one=[r for r in one if r['history_risk_features'][guard_index]==0]
 choices.update(GUARD_RULE_HALF=min(guard_half,key=lambda r:r['labels']['short_JF'])['tag'] if guard_half else None,GUARD_RULE_ONE=min(guard_one,key=lambda r:r['labels']['short_JF'])['tag'] if guard_one else None)
 methods={};lookup={r['tag']:r for r in half}
 for name,tag in choices.items():
  if tag is None:
   methods[name]=dict(choice='ABSTAIN',qualified=False,full_remaining_JF=None,full_remaining_JM=None,full_JF=None,full_JM=None,native_peak_already_failed_by_H=False,physical_execution_hash='ABSTAIN',failed_requirements=['NO_SUPPORTED_QUALIFIED_CONTINUATION'],completion='not a successful completed task');continue
  r=lookup[tag];methods[name]=dict(choice=tag,qualified=r['qualified'],full_remaining_JF=r['labels']['full_remaining_JF'],full_remaining_JM=r['labels']['full_remaining_JM'],native_peak_already_failed_by_H=r['labels']['native_peak_ratio_already_by_H_evaluation_only']>1+1e-7,physical_execution_hash=physical_hash(r['id']),**r['metrics'])
 e=methods['E_REAL_FULL_REFERENCE'];dc=methods['D_CRITIC'];gains={k:(v['full_remaining_JF']-dc['full_remaining_JF'] if dc['qualified'] and v['qualified'] else None) for k,v in methods.items() if k.startswith('A_FIXED') or k in ['B_HALF_SECOND','C_ONE_SECOND','FIXED_TRAINING_CHOICE','GUARD_RULE_HALF','GUARD_RULE_ONE']};live=[];events=[json.loads(l) for l in (P/'runtime/ATTEMPTS.jsonl').read_text().splitlines()];start=min(r['unix'] for r in events if r['event']=='START' and r.get('group')==g);assert start>frozen['frozen_unix'],'TEST_STARTED_BEFORE_MODEL_FROZEN'
 for pred,r in zip(d['rows'],half):
  path=P/'predictions'/(r['id']+'_H05.json');assert path.exists(),'MISSING_PRETAIL_PREDICTION:'+r['id'];old=json.loads(path.read_text());errors=[abs(np.array(old['cost']['mean'])-np.array(pred['mean'])).max(),abs(old['short_JF']-r['labels']['short_JF']),max(abs(np.array(old['local_risk_features'])-np.array(r['local_risk_features']))),max(abs(np.array(old['history_risk_features'])-np.array(r['history_risk_features'])))];assert max(errors)<1e-7,('LIVE_PREDICTION_REPLAY_MISMATCH',r['id'],errors)
  end=next(e['unix'] for e in events if e['event']=='END' and e['id']==r['id']);assert old['created_unix']<end,'PREDICTION_NOT_BEFORE_REAL_END';live.append({'id':r['id'],'max_abs_replay_error':float(max(errors)),'saved_before_full_branch_END':True,'inference_wall_s':old['inference_wall_s']})
 err=np.array([p['mean'][0]-r['labels']['tail_JF'] for p,r in zip(d['rows'],half)]);center=np.array([p['mean'][3]-r['labels']['tail_JF'] for p,r in zip(d['rows'],half)]);relative=center-center.mean();out={'group':g,'phase':cfg['fork_phase'],'evaluated_unix':time.time(),'model_path':model_path,'model_frozen_unix':frozen['frozen_unix'],'model_sha256':hashlib.sha256((P/model_path).read_bytes()).hexdigest(),'primary_menu':menu,'continuation':cfg.get('continuation_policy','original B rolling/replan'),'methods':methods,'decision':d,'critic_JF_improvement_vs':gains,'critic_regret_E_N_s':dc['full_remaining_JF']-e['full_remaining_JF'] if dc['qualified'] else None,'tail_absolute_RMSE_N_s':float(np.sqrt(np.mean(err**2))),'tail_relative_RMSE_after_common_error_N_s':float(np.sqrt(np.mean(relative**2))),'live_prediction_replay':live,'critic_abstained':dc['choice']=='ABSTAIN','critic_changes_physical_execution_vs_half':dc['choice']!='ABSTAIN' and dc['physical_execution_hash']!=methods['B_HALF_SECOND']['physical_execution_hash'],'critic_changes_physical_execution_vs_one':dc['choice']!='ABSTAIN' and dc['physical_execution_hash']!=methods['C_ONE_SECOND']['physical_execution_hash'],'critic_changes_physical_execution_vs_training_fixed':dc['choice']!='ABSTAIN' and dc['physical_execution_hash']!=methods['FIXED_TRAINING_CHOICE']['physical_execution_hash'],'physical_attempt_savings':0,'all_offered_candidates_completed_for_reference':True,'future_qualification_mask_in_deployed_choices':False,'E_scope':'finite actually executed qualified menu only; not a deployable method or global optimum'}
 if not legacy:
  ab=json.loads((P/'models/COMMON_COMPOSE_NO_HISTORY_FROZEN.json').read_text())['phases'][cfg['fork_phase']];out['no_history_ablation']=select(ab,inp)
 put('analysis/evaluation/'+g+'.json',out);print('FROZEN_EVAL',g,{k:v['choice'] for k,v in methods.items()},'gains',gains,'qualified',dc['qualified'],flush=True);return out
if __name__=='__main__':evaluate(sys.argv[1],sys.argv[2],len(sys.argv)>3 and sys.argv[3]=='legacy')
