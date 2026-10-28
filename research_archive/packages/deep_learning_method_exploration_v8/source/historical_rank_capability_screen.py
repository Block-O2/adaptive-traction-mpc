"""Retrospective development diagnostic; no training or physics, no future decision mask."""
from pathlib import Path
import json,hashlib,time,os,itertools
P=Path(__file__).resolve().parents[1];root=P.parent

def action_key(a):
 if a.get('family')=='B':return 'B'
 if a.get('family')!='modal8_retimed':return None
 d={'family':a['family'],'x':a['x'],'legacy':a.get('legacy',[0.,0.]),'smooth_strength':a.get('smooth_strength',0.),'anticipatory':a.get('anticipatory',False),'slot_overrides':a.get('slot_overrides',[])}
 return hashlib.sha256(json.dumps(d,sort_keys=True).encode()).hexdigest()
lib=json.loads((root/'smoothness_critic_integration_v6/freeze/LIBRARY.json').read_text())['library']
lookup={action_key(a):tag for tag,a in lib.items()}
for n in ['REF025','ANT']:
 a=json.loads((root/'smoothness_critic_research_v5/attempts'/('STRICT01_'+n+'_RESULT.json')).read_text())['action'];lookup[action_key(a)]=n
rows=[]
sets={'smoothness_critic_research_v5':['HANDOFF01','STRICT01','VAL01','VAL02','VAL03','VAL04'],'smoothness_critic_integration_v6':['DEV_O1','SMOOTH_A1','SMOOTH_A2','PHASE_RULE_S1','PHASE_RULE_S2']}
for pkg,groups in sets.items():
 Q=root/pkg
 for g in groups:
  config=json.loads((Q/'experiments'/f'{g}.json').read_text());out={};identities=[]
  for f in sorted((Q/'attempts').glob(g+'_*_RESULT.json')):
   r=json.loads(f.read_text());id=r['id'];a=r.get('action',{});key=action_key(a);tag=lookup.get(key)
   if g.startswith('PHASE_RULE'):
    if id.endswith('_HANDOFF'):tag='V6PHASE'
   if tag is None or not r.get('complete'):continue
   mf=Q/r['metrics_path'];m=json.loads(mf.read_text());sf=Q/'runtime/reports'/f'{id}_SNAPSHOT.json';ss=json.loads(sf.read_text());integration=ss['manifest']['native_integration']['sha256'];identities.append(integration)
   out[tag]={'id':id,'JF':r['JF'],'JM':r['JM'],'qualified':r['qualified'],'motion_failed':r.get('motion_vs_B',{}).get('failed_requirements',[]),'jerk_RMS':m['motion']['raw']['full']['jerk_deg_s3']['rms'],'source':str(f),'native_integration_sha256':integration,'policy_input':a,'policy_semantics':'full frozen policy commitment' if tag!='V6PHASE' else 'OUT1_HANDOFF_then_COMPOSE'}
  if not out:continue
  assert len(set(identities))==1,(pkg,g,'mixed actual parents')
  rows.append({'package':pkg,'group':g,'integration_sha256':identities[0],'condition':config['condition'],'outcomes':out,'status':'Retrospective exposed development only; no new independent evidence'})
pairs=[]
tags=sorted(set(t for r in rows for t in r['outcomes']))
for a,b in itertools.combinations(tags,2):
 comparisons=[]
 seen={}
 for r in rows:
  if a not in r['outcomes'] or b not in r['outcomes']:continue
  aa,bb=r['outcomes'][a],r['outcomes'][b];sig=r['integration_sha256']
  # Same integration may still have different controller state/prefix, so retain group list;
  # never count repeat integration as independent. All repeated orientations checked.
  d=aa['JF']-bb['JF'];sign=1 if d>.02 else -1 if d<-.02 else 0
  comparisons.append({'group':r['group'],'package':r['package'],'integration_sha256':sig,'delta_JF_A_minus_B':d,'delta_JM_A_minus_B':aa['JM']-bb['JM'],'both_qualified':aa['qualified'] and bb['qualified'],'qualified_A':aa['qualified'],'qualified_B':bb['qualified'],'orientation_at_0p02_Ns':sign})
  seen.setdefault(sig,set()).add(sign)
 distinct=[r for i,r in enumerate(comparisons) if r['integration_sha256'] not in [z['integration_sha256'] for z in comparisons[:i]]]
 qualified=[r for r in distinct if r['both_qualified']]
 pair={'A':a,'B':b,'comparisons':comparisons,'distinct_integration_states':len(distinct),'both_qualified_distinct':len(qualified),'qualified_cost_order_flip':{r['orientation_at_0p02_Ns'] for r in qualified}>={-1,1},'all_complete_cost_order_flip':{r['orientation_at_0p02_Ns'] for r in distinct}>={-1,1},'qualification_pattern_varies':len({(r['qualified_A'],r['qualified_B']) for r in distinct})>1}
 if comparisons:pairs.append(pair)
result={'event':'HISTORICAL_RANK_CAPABILITY_SCREEN','status':'COMPLETED_RETROSPECTIVE_NOT_TRAINED','unix':time.time(),'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'rows':rows,'pairs':pairs,'qualified_order_flip_pairs':[{'A':r['A'],'B':r['B']} for r in pairs if r['qualified_cost_order_flip']],'qualification_flip_pairs':[{'A':r['A'],'B':r['B']} for r in pairs if r['qualification_pattern_varies']],'limitations':['Historical exposed outcomes only; no new independent-model test','MuJoCo integration identity prevents counting trivial aliases as new physics; same integration may mask distinct controller states and is conservatively merged','JF orientation threshold 0.02 Ns from historical critic materiality convention, not new task qualification','Future qualification used only for retrospective capability audit, never as a deployed mask','No aggregate scalarization of JF/JM/jerk','Different upstream/tail-policy critic labels intentionally excluded']}
(P/'analysis/HISTORICAL_RANK_CAPABILITY_SCREEN.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
with (P/'RESEARCH_DECISIONS.jsonl').open('a') as f:f.write(json.dumps({'event':'BRANCH_RESULT','unix':time.time(),'id':result['event'],'status':result['status'],'rows':len(rows),'unique_native_integration_states':len({r['integration_sha256'] for r in rows}),'qualified_cost_order_flip_pairs':result['qualified_order_flip_pairs'],'qualification_flip_pairs':result['qualification_flip_pairs'],'best_baseline':'State-specific traditional Pareto library, not one uniform best objective','next_question':'Do new varied-Human or RETURN timing states expose a causal, nontrivial ranking difference?','training':0,'new_physics':0})+'\n')
print(json.dumps({'groups':len(rows),'states':len({r['integration_sha256'] for r in rows}),'qualified_cost_flips':result['qualified_order_flip_pairs'],'qualification_flips':result['qualification_flip_pairs']},indent=2))
