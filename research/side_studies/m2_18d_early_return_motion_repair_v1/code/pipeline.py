from study_common import *
import matched_harness as mh
import copy,random,subprocess,signal,traceback
S=STUDY;P=json.loads((S/'SEARCH_PROTOCOL.json').read_text());rng=np.random.default_rng(P['search_seed'])
def put(n,x):mh.put(S/n,x)
def rows():return [json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()]
def cat():return {c['id']:c for c in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']}
def count():return sum(r['event']=='START' for r in mh.records())
def can_dispatch(n=1):return count()+n<=252 and time.time()+max(180,n*110)<P['dispatch_cutoff_unix']-900
def execute(mode,candidates=None):
 if candidates is not None:put('queue/'+mode+'.json',dict(candidates=candidates,registered_unix=time.time(),no_heldout_used=True))
 with (S/'logs'/(mode+'.log')).open('a') as log:
  p=subprocess.Popen([sys.executable,str(S/'code/worker.py'),mode],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  put('PIPELINE_CHILD.json',dict(pid=p.pid,pgid=p.pid,parent_pid=os.getpid(),mode=mode,status='RUNNING',unix=time.time()))
  try:rc=p.wait(timeout=min(3600,P['hard_stop_unix']-time.time()-300))
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=5)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise RuntimeError('OWNED_BATCH_TIMEOUT:'+mode)
  finally:put('PIPELINE_CHILD.json',dict(pid=None,pgid=None,parent_pid=os.getpid(),mode=mode,status='JOINED',unix=time.time()))
  if rc:raise RuntimeError('WORKER_FAILURE:'+mode)
 print(json.dumps(dict(phase=mode,status='COMPLETE',attempts=count())),flush=True)
def to_raw(c):
 c=copy.deepcopy(c)
 if 'table' in c:
  c['phases']={ph:[dict(kind='PWL',amplitude=max(abs(np.asarray(a)*.2)),shape='K3',knots=[.1,.4,.7],support=[0,1],values=(np.asarray(a)*.2).tolist(),domain='remaining_causal_progress') if any(a) else None for a in c['table'][i]] for i,ph in enumerate(['OUTBOUND','RETURN'])};del c['table']
 return c
def active(c):return [(ph,i) for ph,ss in c['phases'].items() for i,s in enumerate(ss) if s is not None and any(s['values'])]
def problem_slots(raw,mech,sid):
 slots=active(raw);match=next((r for r in mech if r['id']=='baseline_'+sid),None)
 ranked=[(r['phase'],r['native_index']) for r in (match or {}).get('slot_scores',[]) if (r['phase'],r['native_index']) in slots]
 return list(dict.fromkeys(ranked+slots))
def candidate(source,ident,changes):
 c=to_raw(source);c.update(id=ident,stage=ident.split('_')[0].upper(),parameters=dict(source=source.get('parameters',{}).get('source',source['id']),direct_parent=source['id'],changes=changes));return c
def scale_spec(c,ph,i,f):
 s=c['phases'][ph][i]
 if s is not None:s['values']=np.clip(np.asarray(s['values'])*f,-.2,.2).tolist();s['amplitude']=float(max(abs(np.asarray(s['values']))))
def expand_slot(c,ph,i,delta,shape='flat'):
 c['phases'].setdefault(ph,[None]*5)
 patterns={'flat':[1,1,1],'taper':[1,.6,.2],'ramp':[.2,.6,1],'tent':[.2,1,.2]}
 c['phases'][ph][i]=dict(kind='PWL',amplitude=delta,shape=shape,knots=[.1,.4,.7],support=[0,1],values=(delta*np.asarray(patterns[shape])).tolist(),domain='remaining_causal_progress')
def family(c):return tuple((ph,tuple(i for i,s in enumerate(ss) if s is not None and any(s['values']))) for ph,ss in sorted(to_raw(c)['phases'].items()))
def choose_frozen():
 rr=[r for r in rows() if r['stage']!='REFERENCE' and r['candidate_id'] not in ['C4_1_5','C4_repeat'] and r['comparison']['actual_nonzero_count']>0];cc=cat();eligible=[r for r in rr if r['comparison']['eligible']];chosen=[]
 if eligible:
  chosen.append(min(eligible,key=lambda r:(-r['comparison']['gain_percent'],r['continuous_constraints']['worst_ratio'])))
  smooth=min(eligible,key=lambda r:(r['continuous_constraints']['worst_ratio'],-r['comparison']['gain_percent']))
  if smooth not in chosen:chosen.append(smooth)
  near=[r for r in rr if not r['comparison']['acceptance_pass'] and r['comparison']['gain_percent']>=2]
  if near:chosen.append(min(near,key=lambda r:(r['continuous_constraints']['worst_ratio'],-r['comparison']['gain_percent'])))
  elif len(chosen)<3:
   for r in sorted(eligible,key=lambda r:-r['comparison']['gain_percent']):
    if r not in chosen and family(cc[r['candidate_id']])!=family(cc[chosen[0]['candidate_id']]):chosen.append(r);break
 elif rr:chosen=[min(rr,key=lambda r:(r['continuous_constraints']['worst_ratio'] if r['comparison']['gain_percent']>=2 else 100+r['continuous_constraints']['worst_ratio'],-r['comparison']['gain_percent']))]
 frozen=dict(unix=time.time(),candidate_parameters_frozen_before_V=True,no_V_used=True,status='SUCCESS_CANDIDATES_PENDING_TEST' if eligible else 'NEGATIVE_DIAGNOSTIC_ONLY',candidates=[cc[r['candidate_id']] for r in chosen[:3]],discovery_rows=chosen[:3],eligible_new_count=len(eligible),rule=P['selection_rule'])
 put('FROZEN_SELECTION.json',frozen);return frozen
def main():
 from mechanism import analyze
 mech=analyze('baseline');cc=cat();hist=json.loads((S/'HISTORICAL_E_RECOVERY.json').read_text());old=dict(id='Historical_E_replay',stage='REFERENCE',table=np.asarray(hist['table_flat']).reshape(2,5,3).tolist(),parameters={'historical_source':hist['name']})
 seeds=[cc[k] for k in ['M2_fixed_actions','C2_pair_1_2','C2_fixed_07','C2_pair_0_3','C4_1_5']]
 basegain={r['candidate_id']:r['comparison']['gain_percent'] for r in rows() if r['id'].startswith('baseline_')}
 put('SEED_FAMILIES.json',dict(seeds=seeds,baseline_gains=basegain,actual_family_rule='phase, active issued slots, native sampled/activated delta and support, not just parameter names'))
 # Two bounded mechanism batches: one-slot cancellation, amplitude and phase isolation.
 for batch in range(2):
  if (S/('mechanism'+str(batch+1)+'_DONE.json')).exists():continue
  candidates=[old] if batch==0 else []
  for j,seed in enumerate(seeds[:-1]):
   raw=to_raw(seed);slots=problem_slots(raw,mech,seed['id'])
   for k in range(6):
    ph,i=slots[(k+batch*3)%len(slots)];c=candidate(raw,f'mechanism{batch+1}_{j}_{k}',dict(operation='cancel_one_slot' if k<3 else 'scale_one_slot',phase=ph,slot=i,factor=0 if k<3 else [.5,.75,1.25][k-3],batch=batch+1))
    if k<3:c['phases'][ph][i]=None
    else:scale_spec(c,ph,i,[.5,.75,1.25][k-3])
    if batch==1 and k==5:
     only='OUTBOUND' if j%2==0 else 'RETURN';c['phases']={ph:ss for ph,ss in c['phases'].items() if ph==only};c['parameters']['changes']=dict(operation='phase_isolation',kept=only)
    candidates.append(c)
  if not can_dispatch(len(candidates)+2):break
  mode='mechanism'+str(batch+1)
  if mode=='mechanism2' and (S/'WRAPPER_REPAIR2_REGISTERED.json').exists():
   candidates=json.loads((S/'queue/mechanism2.json').read_text())['candidates'];mode='mechanism2_resume'
  execute(mode,candidates);analyze(mode)
 # Four adaptive repair batches. Keep a named force-retention tier for every chain.
 stall={s['id']:0 for s in seeds};bestscore={s['id']:float('inf') for s in seeds}
 for batch in range(4):
  cc=cat();rr=rows();candidates=[];tier=[.75,.5,.25,.25][batch]
  for j,seed in enumerate(seeds):
   sid=seed['id'];poss=[r for r in rr if r['candidate_id']==sid or cc.get(r['candidate_id'],{}).get('parameters',{}).get('source')==sid]
   retained=[r for r in poss if r['comparison']['gain_percent']>=max(0,basegain[sid]*tier)]
   picked=min(retained or poss,key=lambda r:(not r['comparison']['acceptance_pass'],r['continuous_constraints']['worst_ratio'] if not r['comparison']['acceptance_pass'] else -r['comparison']['gain_percent'],r['continuous_constraints']['positive_violation_sum']))
   center=cc[picked['candidate_id']];score=picked['continuous_constraints']['worst_ratio'] if not picked['comparison']['acceptance_pass'] else 1-picked['comparison']['gain_percent']/100
   improved=score<bestscore[sid]-1e-8;stall[sid]=0 if improved else stall[sid]+4;bestscore[sid]=min(score,bestscore[sid]);raw=to_raw(center);slots=problem_slots(raw,mech,sid)
   for k in range(4):
    ph,i=slots[(batch+k)%len(slots)];op=['slot_scale','adjacent_redistribution','support_shift','correlated_amplitude'][k];c=candidate(raw,f'repair{batch+1}_{j}_{k}',dict(operation=op,phase=ph,slot=i,tier=tier,stall_count=stall[sid],neighborhood_changed=stall[sid]>=12));c['parameters']['source']=sid
    if op=='slot_scale':scale_spec(c,ph,i,[.65,.8,.5,1.15][batch] if sid!='C4_1_5' else [1.2,1.3,1.5,1.1][batch])
    elif op=='adjacent_redistribution':
     nxt=(i+1)%5;sp=copy.deepcopy(c['phases'][ph][i]);scale_spec(c,ph,i,.7);vals=np.asarray(sp['values'])*.3
     if c['phases'][ph][nxt] is None:c['phases'][ph][nxt]=sp;c['phases'][ph][nxt]['values']=vals.tolist()
     else:c['phases'][ph][nxt]['values']=np.clip(np.asarray(c['phases'][ph][nxt]['values'])+vals,-.2,.2).tolist()
    elif op=='support_shift':
     sp=c['phases'][ph][i];sp['support']=[max(0,sp['support'][0]+[.05,-.05,.1,-.1][batch]),min(1,sp['support'][1]+[-.05,.05,-.1,.1][batch])]
    else:
     noise=rng.normal(0,.12,len(slots));noise=(noise+np.roll(noise,1))/2
     for (p,i),n in zip(slots,noise):scale_spec(c,p,i,max(.25,(1 if sid=='C4_1_5' else [.9,.75,.6,.9][batch])+n))
    candidates.append(c)
  # Joint O/R candidates are executed in full, no adding independent gains.
  feasible=[r for r in rr if r['comparison']['acceptance_pass'] and r['candidate_id'] in cc]
  for k in range(2):
   source=cc[min(feasible,key=lambda r:-r['comparison']['gain_percent'])['candidate_id']] if feasible else seeds[-1]
   c=candidate(source,f'repair{batch+1}_joint_{k}',dict(operation='add_weak_opposite_phase_slot',slot=batch%5,amplitude=[-.005,.005][k]));expand_slot(c,'OUTBOUND',batch%5,[-.005,.005][k],'taper');candidates.append(c)
  if not can_dispatch(len(candidates)+2):break
  put('REPAIR_ADAPTATION_'+str(batch+1)+'.json',dict(tier=tier,stall=stall,bestscore=bestscore,rule=P['repair_downgrade'],candidates=len(candidates)));execute('repair'+str(batch+1),candidates)
 # 58 reexploration candidates: 34 local/cross-slot +24 undercovered (41.4%).
 for batch,n in enumerate([20,20,18]):
  cc=cat();rr=[r for r in rows() if r['candidate_id'] in cc];leaders=[];used=set()
  for r in sorted(rr,key=lambda r:(not r['comparison']['acceptance_pass'],-r['comparison']['gain_percent'] if r['comparison']['acceptance_pass'] else r['continuous_constraints']['worst_ratio'])):
   key=family(cc[r['candidate_id']])
   if key not in used:leaders.append(cc[r['candidate_id']]);used.add(key)
   if len(leaders)==3:break
  candidates=[];local=n-8
  for k in range(n):
   if k<local:
    source=leaders[k%len(leaders)];c=candidate(source,f'reexplore{batch+1}_{k}',dict(operation='local_or_cross_slot',region=family(source)));slots=active(c)
    for ph,i in slots:scale_spec(c,ph,i,float(np.clip(1+rng.normal(0,.12),.4,1.6)))
    if k%3==0:
     ph,i=slots[k%len(slots)];nxt=(i+1)%5
     if c['phases'][ph][nxt] is None:expand_slot(c,ph,nxt,float(rng.choice([-.005,.005,-.01,.01])),'ramp')
   else:
    c=dict(id=f'reexplore{batch+1}_{k}',stage='REEXPLORE',phases={},parameters={'source':'UNDERCOVERED','changes':{'operation':'registered_broad_phase_slot_pair','allocation':'broad'}})
    for ph in ['OUTBOUND','RETURN'] if k%2 else ['OUTBOUND' if batch%2 else 'RETURN']:
     i=int(rng.integers(0,5));amp=float(rng.choice([-.018,-.012,-.006,.006,.012,.018,.03,-.03]));expand_slot(c,ph,i,amp,['flat','taper','ramp','tent'][k%4])
     if k%3==0:expand_slot(c,ph,(i+2)%5,-amp*.4,'taper')
   candidates.append(c)
  if not can_dispatch(n+2):break
  put('REEXPLORATION_REGIONS_'+str(batch+1)+'.json',dict(local=local,broad=8,actual_parameter_regions=[family(c) for c in leaders],actual_regions_claim_pending_native_audit=True));execute('reexplore'+str(batch+1),candidates)
 frozen=choose_frozen()
 import analyze_matched as am
 rr=[r for r in rows() if r['stage']!='REFERENCE' and set(cat()[r['candidate_id']].get('phases',{}))=={'RETURN'}]
 if rr:
  r=max(rr,key=lambda r:r['comparison']['gain_percent']);group=r['id'].split('_')[0];negative=am.negcontrol(r['id'],group+'_B0_repeat_1');put('NEW_RETURN_NEGATIVE_CONTROL.json',negative);assert negative['all_pre_intervention_fields_exact_equal'],'NEW_RETURN_PREFIX_MISMATCH'
 execute('verify')
 for condition in P['validation_conditions']:
  if count()+len(frozen['candidates'])+3>300 or time.time()+600>P['dispatch_cutoff_unix']:break
  execute(condition['name'])
 put('PIPELINE_DONE.json',dict(unix=time.time(),attempts=count(),heldout_reselection=False,no_further_physics=True))
try:main()
except BaseException as e:
 put('PIPELINE_ERROR.json',dict(unix=time.time(),error=str(e),traceback=traceback.format_exc(),no_new_dispatch=True));raise
