"""Bounded session calibration; no relabeling of committed-suffix value targets."""
from freeze import *
import sys,collections
sys.path.insert(0,str(STUDY/'code'))
from accounting import attempts
def result(name):
 p=STUDY/'output'/(name+'_RESULT.json');return json.loads(p.read_text()) if p.exists() else None
def qualified(r):
 m={} if r is None else r.get('metric',{});return bool(m.get('valid') and m.get('matched_eligible') and m.get('status')=='COMPLETE')
def enqueue(name,method,weights,seed,scale=1.,baseline=False):
 path=STUDY/'queue'/(name+'.json')
 if path.exists():return
 request=dict(id=name,kind='physics',mode='table' if baseline else 'search',method=method,seed=seed,weights=weights,value_scale=scale,group='exposed_human_session_pilot',split='pilot',pilot=True,prefix={'OUTBOUND':[[.025]*3,[-.015]*3]},result_path=str(STUDY/'output'/(name+'_RESULT.json')))
 contract=json.loads((STUDY/'PILOT_CONTRACT.json').read_text());request['algorithm_sources']=contract['algorithm_sources'];request['pilot_contract_sha256']=sha(STUDY/'PILOT_CONTRACT.json')
 assert all(sha(Path(p))==h for p,h in contract['algorithm_sources'].items()),'PILOT_FROZEN_ALGORITHM_CHANGED'
 if weights:assert sha(Path(weights))==contract['weights_sha256'],'PILOT_FROZEN_WEIGHTS_CHANGED'
 save(path,request)
def await_results(names,cfg):
 while time.time()<cfg['dispatch_cutoff_unix']:
  records=[result(name) for name in names]
  if all(r is not None for r in records):return records
  time.sleep(30)
 raise RuntimeError('PILOT_CLOSEOUT_TIME')
def main():
 cfg=json.loads((STUDY/'RUN_PLAN.json').read_text());path=STUDY/'PILOT_STATE.json';state=json.loads(path.read_text()) if path.exists() else dict(status='CHECK_PROMOTION',rounds=[],original_start_unix=1791222386)
 if state['status']=='CHECK_PROMOTION':
  analyses=[json.loads((STUDY/f'ANALYSIS_v2_{batch}.json').read_text()) for batch in ('final','independent','fresh')]
  eligible=set.intersection(*(set(a['eligible_pilot_methods']) for a in analyses));remaining=cfg['deadline_unix']-time.time()
  # A PGV win versus P can come entirely from G. The user's direction-only
  # branch forbids calling that a value-learning success. Require the same
  # frozen 0.5% engineering scale for the incremental V contribution.
  value_evidence={};value_qualified=[]
  for method,base_method in (('P+V','P'),('P+G+V','P+G')):
   batches=[]
   for a in analyses:
    arms={(r['group'],r['method']):r for r in a['rows']};groups=sorted({r['group'] for r in a['rows']});gains=[];all_qualified=True
    for group in groups:
     base=arms.get((group,base_method));current=arms.get((group,method))
     if not base or not current or not base['valid'] or not current['valid']:all_qualified=False;continue
     gains.append((base['metric']['J_F']-current['metric']['J_F'])/base['metric']['J_F'])
    mean=sum(gains)/len(gains) if gains else None;passed=all_qualified and len(gains)>=4 and all(g>0 for g in gains) and mean>=.005
    batches.append(dict(batch=a['batch'],base_method=base_method,paired_gains=gains,mean_gain=mean,all_pairs_qualified=all_qualified,passed=passed))
   value_evidence[method]=batches
   if method in eligible and all(b['passed'] for b in batches):value_qualified.append(method)
  state.update(value_attribution_evidence=value_evidence,value_qualified_methods=value_qualified,primary_eligible_methods=sorted(eligible));save(path,state)
  if not eligible or remaining<3*3600 or 300-attempts()<15:
   state.update(status='NOT_STARTED',reason='no consistent promotion across original/independent/fresh batches' if not eligible else 'less than three hours or insufficient physical budget',eligible=sorted(eligible),remaining_seconds=remaining);save(path,state);print(json.dumps(state));return
  values=value_qualified
  if not values:
   direction='P+G' in eligible
   state.update(status='FROZEN_DIRECTION_VALIDATION_COMPLETE' if direction else 'NOT_STARTED',reason='no consistent incremental V benefit across required batches; frozen G validation complete' if direction else 'primary combined gain does not establish consistent incremental V contribution',eligible=sorted(eligible));save(path,state);print(json.dumps(state));return
  method=max(values,key=lambda m:analyses[-1]['methods'][m]['mean_paired_gain_fraction']);contract=json.loads((STUDY/'COMPARISON_v2_fresh.json').read_text());weights=contract['weights']
  manifest=dict(method=method,weights=weights,weights_sha256=contract['weights_sha256'],maximum_total_physical_attempts=15,baseline_rounds=1,adaptation_rounds=5,validation_pairs=2,G_frozen=True,within_round_parameters_fixed=True,feedback_replanning=True,candidate_budget=dict(population=8,generations=2,G_max=3),individual_part='bounded scalar lambda multiplying existing deltaV; no neural refit',update_rule='round 2 lambda=1, later choose best qualified paired-gain lambda plus alternating [.25,-.25,.125,-.125], clip [.5,1.5]; retain best measured pair, not last',label_semantics='Session cost calibrates one policy parameter. Replanning-round returns are never substituted as Monte Carlo labels for committed-suffix V. Existing pi_cont/weights remain frozen.',round_seeds='each adaptation/control pair shares a fresh search seed; same physical initial state and legal prefix',exposure='nominal Human already present in offline labels; no new-human generalization',controls='one shared B baseline; all five update rounds and both final validations get independent no-update lambda=1 controls')
  manifest['algorithm_sources']=contract['algorithm_sources']
  manifest['value_attribution_evidence']=value_evidence;manifest['value_engineering_threshold']=.005
  save(STUDY/'PILOT_CONTRACT.json',manifest);state.update(status='RUNNING',method=method,weights=weights,next_round=1,best_scale=1.,best_gain=0.,best_round=2);save(path,state)
 try:
  if state['next_round']==1:
   name='120_pilot_round1_shared_B';enqueue(name,'B',None,2026110001,baseline=True);r=await_results([name],cfg)[0];state['baseline']=dict(id=name,qualified=qualified(r),metric=r.get('metric'));state['next_round']=2;save(path,state)
  for round_no in range(state['next_round'],7):
   scale=1. if round_no==2 else float(max(.5,min(1.5,state['best_scale']+[.25,-.25,.125,-.125][round_no-3])))
   seed=2026110000+round_no;names=[f'120_pilot_round{round_no}_adapt',f'120_pilot_round{round_no}_control']
   if attempts()+2>300:raise RuntimeError('PILOT_PHYSICAL_BUDGET')
   enqueue(names[0],state['method'],state['weights'],seed,scale);enqueue(names[1],state['method'],state['weights'],seed,1.)
   active,control=await_results(names,cfg);valid=qualified(active) and qualified(control);gain=(control['metric']['J_F']-active['metric']['J_F'])/control['metric']['J_F'] if valid else None
   record=dict(round=round_no,ids=names,seed=seed,lambda_fixed=scale,qualified_pair=valid,gain_vs_no_update=gain,adapt_metric=active.get('metric'),control_metric=control.get('metric'));state['rounds'].append(record)
   if valid and gain>state['best_gain']:state.update(best_scale=scale,best_gain=gain,best_round=round_no)
   state['next_round']=round_no+1;save(path,state)
  state['frozen_scale']=state['best_scale'];state.setdefault('validation',[]);save(path,state)
  for index in range(len(state['validation']),2):
   seed=2026110100+index;names=[f'120_pilot_validate{index}_adapt',f'120_pilot_validate{index}_control']
   if attempts()+2>300:raise RuntimeError('PILOT_PHYSICAL_BUDGET')
   enqueue(names[0],state['method'],state['weights'],seed,state['frozen_scale']);enqueue(names[1],state['method'],state['weights'],seed,1.);active,control=await_results(names,cfg);valid=qualified(active) and qualified(control)
   state['validation'].append(dict(ids=names,seed=seed,qualified_pair=valid,gain_vs_no_update=(control['metric']['J_F']-active['metric']['J_F'])/control['metric']['J_F'] if valid else None,adapt_metric=active.get('metric'),control_metric=control.get('metric')));save(path,state)
  state.update(status='COMPLETE',claim='exposed-human scalar policy calibration pilot; value networks/committed-suffix targets frozen; no statistical/generalization claim');save(path,state)
 except BaseException as error:state.update(status='PARTIAL_RESUMABLE',error=str(error));save(path,state);raise
 print(json.dumps({k:v for k,v in state.items() if k not in ('rounds','validation','baseline')}))
if __name__=='__main__':main()
