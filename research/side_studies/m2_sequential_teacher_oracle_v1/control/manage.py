from pathlib import Path
import json,copy,time,sys,hashlib
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_sequential_teacher_oracle_v1')
P=json.loads((S/'SEARCH_PROTOCOL.json').read_text());cat={c['id']:c for c in json.loads((S/'CANDIDATE_CATALOG.json').read_text())['candidates']}
def load(n):return json.loads((S/n).read_text())
def put(n,x):(S/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def rows():return [json.loads(l) for l in (S/'EVALUATIONS.jsonl').read_text().splitlines()] if (S/'EVALUATIONS.jsonl').exists() else []
def spec(v):return dict(kind='PWL',amplitude=v,shape='wide_scalar_plateau',knots=[.001,.5,.999],values=[v]*3,support=[0,1],domain='remaining_causal_progress')
def mod(c,ident,ph,slot,v):
 d=copy.deepcopy(c);d.update(id=ident,stage=MODE,parameters=dict(family=MODE,source=c['id'],phase=ph,slot=slot,amplitude=v));d.setdefault('phases',{}).setdefault(ph,[None]*5)[slot]=spec(v) if v else None;return d
MODE=sys.argv[1]
if MODE=='status':
 starts=[json.loads(l) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines() if json.loads(l)['event']=='START'];rs=rows()
 print(json.dumps(dict(elapsed_min=(time.time()-P['t0_unix'])/60,attempts=len(starts),last_attempt=starts[-1]['id'] if starts else None,last_results=[dict(id=r['id'],gain=r['comparison']['gain_percent'],motion=r['comparison']['acceptance_pass'],failed=r['comparison']['failed_requirements'],worst=r['continuous_constraints']['worst_ratio'],worst_requirement=r['continuous_constraints']['worst_requirement'],phase=r['phase_J_F_N_s']) for r in rs[-3:]],best_feasible=max([r['comparison']['gain_percent'] for r in rs if r['comparison']['acceptance_pass']],default=None),package_GiB=sum(p.stat().st_size for p in S.rglob('*') if p.is_file())/2**30),ensure_ascii=False))
elif MODE=='seqMore':
 eligible=[r for r in rows() if r['comparison']['acceptance_pass'] and any(d['phase']=='OUTBOUND' and d['physically_executed_nonzero'] for d in r['actual_execution'])];r=max(eligible,key=lambda r:r['comparison']['gain_percent']);parent=copy.deepcopy(r['candidate']);cs=[]
 for a,b,e in [(-.034,-.038,.016),(-.040,-.040,.020)]:
  c=copy.deepcopy(parent);c.update(id=f'seqMore_{len(cs)}',stage=MODE,parameters=dict(family=MODE,source=parent['id'],R1=a,R2=b,R3=e,reason='larger central low-force coordination plus compensating exit, same feasible OUTBOUND ancestor; no R0 peak increase'))
  c['phases']['RETURN']=[None,spec(a),spec(b),spec(e),None];cs.append(c)
 put('queue/'+MODE+'.json',dict(parent_candidate=parent,boundary=['RETURN',0],base_id='baseline_B0_repeat_1',candidates=cs,selected_parent_result=r['id'],registered_unix=time.time()));print(json.dumps(dict(mode=MODE,parent=r['id'],candidates=2)))
elif MODE.startswith('seq'):
 rs=rows();eligible=[r for r in rs if r['comparison']['acceptance_pass'] and any(d['phase']=='OUTBOUND' and d['physically_executed_nonzero'] for d in r['actual_execution']) and r['candidate'].get('phases',{}).get('OUTBOUND') and any(r['candidate']['phases']['OUTBOUND']) and not r['id'].startswith(('V','verify'))]
 # Keep actual informative OUTBOUND prefix even when total best remains RETURN-only.
 if MODE=='seqMargin' and eligible:r=min(eligible,key=lambda r:(r['continuous_constraints']['worst_ratio'],-r['comparison']['gain_percent']))
 elif eligible:r=max(eligible,key=lambda r:r['comparison']['gain_percent'])
 else:r=min([r for r in rs if r['id'].startswith('outbound_')],key=lambda r:(r['continuous_constraints']['worst_ratio'],-r['comparison']['gain_percent']))
 parent=copy.deepcopy(r['candidate']);cs=[]
 if MODE.startswith('seqO'):
  occupied=[i for i,s in enumerate(parent['phases'].get('OUTBOUND',[None]*5)) if s];boundary=['OUTBOUND',(max(occupied) if MODE!='seqO' else min(occupied))+1]
  if boundary[1]>=4:boundary=['RETURN',0]
  for slot in [boundary[1],min(4,boundary[1]+1)] if boundary[0]=='OUTBOUND' else [0,3]:
   for v in [-.008,-.003,.003,.008]:cs.append(mod(parent,f'{MODE}_{slot}_{v:+.3f}',boundary[0],slot,v))
 elif MODE=='seqMargin':
  boundary=['RETURN',0]
  for r0,r1,r2,r3 in [(-.006,-.020,-.022,0),(-.012,-.020,-.022,.008),(-.018,-.022,-.026,.012),(-.012,-.030,-.034,.016),(-.006,-.034,-.038,.016),(0,-.040,-.040,.020),(-.006,-.030,-.034,.012),(0,-.024,-.030,.008)]:
   d=copy.deepcopy(parent);d.update(id=f'seqMargin_{len(cs)}',stage=MODE,parameters=dict(family=MODE,source=parent['id'],R=[r0,r1,r2,r3,0],reason='preserve lower immediate force gain ancestor with motion margin; redistribute early/central/exit coordination'))
   d['phases']['RETURN']=[spec(v) if v else None for v in [r0,r1,r2,r3,0]];cs.append(d)
 else:
  # This parent has already executed all retained OUTBOUND adjustments before live RETURN fork.
  boundary=['RETURN',0]
  for slot in [0,1,2,3]:
   for v in ([-.008,.008] if slot in [0,3] else [-.014,-.026]):cs.append(mod(parent,f'{MODE}_{slot}_{v:+.3f}','RETURN',slot,v))
 q=dict(parent_candidate=parent,boundary=boundary,base_id='baseline_B0_repeat_1',candidates=cs,selected_parent_result=r['id'],registered_unix=time.time(),method='replay complete legal ancestor to actual later request, full live-state fork, evaluate complete remaining task and full integral')
 put('queue/'+MODE+'.json',q);print(json.dumps(dict(mode=MODE,parent=r['id'],boundary=boundary,candidates=len(cs))))
elif MODE=='repair':
 cs=[]
 for seed in ['M2_fixed_actions','C2_pair_1_2','repair2_2_0']:
  c=copy.deepcopy(cat[seed])
  if 'table' in c:
   c['phases']={ph:[dict(kind='PWL',amplitude=max(abs(v*.2) for v in vals),shape='historical',knots=[.1,.4,.7],values=[v*.2 for v in vals],support=[0,1],domain='remaining_causal_progress') if any(vals) else None for vals in c['table'][j]] for j,ph in enumerate(['OUTBOUND','RETURN'])};del c['table']
  for operation in ['remove_entry','distributed_return','distributed_outbound','alternating_exit']:
   d=copy.deepcopy(c);d.update(id=seed+'_'+operation,stage='REPAIR',parameters=dict(family=seed,source=seed,operation=operation))
   if operation=='remove_entry':d['phases']['RETURN'][0]=None
   elif operation=='distributed_return':
    total=sum(sum(sp['values'])/3 for sp in d['phases']['RETURN'] if sp is not None)
    d['phases']['RETURN']=[spec(max(-.2,min(.2,total*w))) for w in [.10,.20,.30,.25,.15]]
   elif operation=='distributed_outbound':
    total=sum(sum(sp['values'])/3 for sp in d['phases']['OUTBOUND'] if sp is not None)
    d['phases']['OUTBOUND']=[spec(max(-.2,min(.2,total*w))) for w in [.10,.20,.30,.25,.15]]
   else:
    d['phases']['OUTBOUND'][4]=spec(-.008);d['phases']['RETURN'][3]=spec(.008);d['phases']['RETURN'][4]=None
   cs.append(d)
 put('queue/repair.json',dict(candidates=cs,registered_unix=time.time()));print(json.dumps(dict(mode=MODE,candidates=len(cs))))
elif MODE=='combined':
 base=json.loads((S/'queue/repair.json').read_text())['candidates'];cs=[]
 for source in ['M2_fixed_actions','C2_pair_1_2']:
  c=copy.deepcopy(next(c for c in base if c['id']==source+'_distributed_outbound'));c.update(id=source+'_combined_sequence_repair',stage='REPAIR',parameters=dict(family=source,source=source,operation='distributed_OUTBOUND_plus_remove_R0_plus_compensating_R3',preserved_lowforce_core='original strong RETURN1/RETURN2 unchanged'))
  c['phases']['RETURN'][0]=None;c['phases']['RETURN'][3]=spec(.020);c['phases']['RETURN'][4]=None;cs.append(c)
 put('queue/combined.json',dict(candidates=cs,registered_unix=time.time(),reason='combine observed burden-removing interventions while retaining strong central low-force actions; no new controller'));print(json.dumps(dict(mode=MODE,candidates=len(cs))))
elif MODE=='freeze':
 assert not (S/'FROZEN_SELECTION.json').exists(),'NO_RESELECTION'
 assert not any(json.loads(l).get('mode','').startswith(('V','verify')) for l in (S/'ATTEMPTS.jsonl').read_text().splitlines() if json.loads(l)['event']=='START'),'NO_HELDOUT_INFLUENCE'
 rs=[r for r in rows() if not r['id'].startswith(('V','verify')) and r['candidate_id']!='Frozen_M2'];valid=[r for r in rs if r['comparison']['acceptance_pass']]
 best=max(valid,key=lambda r:r['comparison']['gain_percent']);chosen=[best]
 outset=[r for r in valid if any(r['candidate'].get('phases',{}).get('OUTBOUND',[]))]
 if outset:
  o=max(outset,key=lambda r:r['comparison']['gain_percent'])
  if o['candidate_id']!=best['candidate_id']:chosen.append(o)
 if len(chosen)<2:
  margin=min(valid,key=lambda r:(r['continuous_constraints']['worst_ratio'],-r['comparison']['gain_percent']))
  if margin['candidate_id']!=best['candidate_id']:chosen.append(margin)
 infeasible=[r for r in rs if not r['comparison']['acceptance_pass'] and r['comparison']['gain_percent']>=2]
 diagnostic=min(infeasible,key=lambda r:(r['continuous_constraints']['worst_ratio'],-r['comparison']['gain_percent'])) if infeasible else None
 put('FROZEN_SELECTION.json',dict(unix=time.time(),no_validation_output_used=True,best_known_only=True,candidates=[r['candidate'] for r in chosen],discovery_results=[r['id'] for r in chosen],diagnostic_candidates=[] if diagnostic is None else [diagnostic['candidate']],diagnostic_results=[] if diagnostic is None else [diagnostic['id']],rule=P['selection_rule'],validation_prefix_contract='RETURN slot0 belongs to legal condition generator; only unconsumed frozen slots are applied; if candidate itself has nonzero R0, report conditioned suffix validation separately and do not claim identical full sequence reproduced'))
 for cond in P['validation_conditions']:
  cs=[dict(id='B0_repeat_1',stage='VALIDATION_REFERENCE',phases={}),cat['NATIVE_SCALAR_18']]+[r['candidate'] for r in chosen if r['candidate_id']!='NATIVE_SCALAR_18']+([] if diagnostic is None else [diagnostic['candidate']])+[dict(id='Frozen_M2',stage='VALIDATION_DIAGNOSTIC',parameters={'frozen_Q':True})]
  put('queue/'+cond['name']+'.json',dict(condition=cond,candidates=cs,registered_unix=time.time()))
 cs=[dict(id='B0_repeat_1',stage='REPEAT_REFERENCE',phases={})]
 for i in [1,2]:
  d=copy.deepcopy(best['candidate']);d['id']='best_repeat_'+str(i);cs.append(d)
 put('queue/verify.json',dict(candidates=cs,registered_unix=time.time()));print(json.dumps(dict(frozen=[r['id'] for r in chosen])))
elif MODE=='compact':
 # Compact only this new package's already audited nonessential generated raw.
 keep={'baseline_parent','baseline_B0_repeat_1','baseline_B0_repeat_2','baseline_NATIVE_SCALAR_18','baseline_Frozen_M2','baseline_C2_pair_1_2','baseline_M2_fixed_actions','baseline_repair2_2_0'}
 keep.update(p.name for p in (S/'source/results').iterdir() if p.name.startswith('baseline_'))
 keep.update(p.name for p in (S/'source/results').iterdir() if p.name.startswith('seq') and p.name.endswith('_parent'))
 rs=rows();valid=[r for r in rs if r['comparison']['acceptance_pass']]
 for r in sorted(valid,key=lambda r:-r['comparison']['gain_percent'])[:3]:keep.add(r['id'])
 if (S/'FROZEN_SELECTION.json').exists():keep.update(load('FROZEN_SELECTION.json')['discovery_results']+load('FROZEN_SELECTION.json').get('diagnostic_results',[]))
 for p in (S/'queue').glob('seq*.json'):
  q=json.loads(p.read_text())
  if q.get('selected_parent_result'):keep.add(q['selected_parent_result'])
 removed=[]
 for p in (S/'source/results').iterdir():
  if not p.is_dir() or p.name in keep or p.name.startswith(('V','verify')):continue
  measured=S/'reports'/(p.name+'_MEASURED.json')
  if not measured.exists():continue
  raw=p/'runtime_artifacts.json.gz'
  if raw.exists():
   removed.append(dict(path=str(raw),size=raw.stat().st_size,sha256=load('reports/'+p.name+'_MEASURED.json')['sources'][str(raw)],reason='new ordinary candidate: dense motion NPZ, trace, summary and receipt ownership audit retained'))
   raw.unlink()
  line=S/'reports'/(p.name+'_EXECUTED_RESIDUAL_RECEIPTS.json')
  if line.exists():
   x=json.loads(line.read_text())
   for r in x['rows']:
    rr=r.pop('actual_command_receipts',[]);r['receipt_count_retained_compact']=len(rr);r['receipt_sequence_sha256']=hashlib.sha256(json.dumps(rr,sort_keys=True).encode()).hexdigest()
   x['compacted_after_full_dense_ownership_audit']=True;put('reports/'+line.name,x)
 with (S/'COMPACTION.jsonl').open('a') as f:f.write(json.dumps(dict(unix=time.time(),removed=removed,history_untouched=True))+'\n')
 print(json.dumps(dict(compacted=len(removed),bytes=sum(r['size'] for r in removed))))
else:raise ValueError(MODE)
