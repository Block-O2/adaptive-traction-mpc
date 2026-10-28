"""Transparent phase-library ranking using only the actual pre-decision context.
This is a traditional small lookup proxy, not a terminal-state critic or new Q network.
"""
from pathlib import Path
import json,time,hashlib,os,resource
import numpy as np
P=Path(os.environ.get('ACL2_PACKAGE',str(Path(__file__).resolve().parents[1])))
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def context_vector(c):return np.r_[c['task_s'],c['causal_estimated_state']].tolist()
def canonical(action,phase):
 ix=[0,1,4,6] if phase=='OUTBOUND' else [2,3,5,7]
 return tuple(action['x'][i] for i in ix)+tuple(action.get('legacy',[0.,0.]))
def fit_proxy(training_groups,additional_groups=()):
 started=time.perf_counter();usage_start=resource.getrusage(resource.RUSAGE_SELF)
 menu=json.loads((P/'freeze/PRIMARY_MENU.json').read_text())['primary_menu'];lib=json.loads((P/'freeze/LIBRARY.json').read_text())['library'];phases={};sources=[]
 for phase in ['OUTBOUND','RETURN']:
  rows=[];contexts=[]
  for g in list(training_groups)+list(additional_groups):
   cfg=json.loads((P/'experiments'/f'{g}.json').read_text())
   if cfg['fork_phase']!=phase or (phase=='RETURN' and cfg.get('upstream_policy')!='COMPOSE'):continue
   context=json.loads((P/'audit'/f'{g}_FORK_CONTEXT.json').read_text());data=[r for r in json.loads((P/'data'/f'{g}.json').read_text()) if r['horizon_s']==.5];b=next(r for r in data if r['tag']=='B');contexts.append(context_vector(context));sources.append(g)
   for r in data:
    if r['tag'] in menu:rows.append(dict(group=g,tag=r['tag'],gain_vs_B_N_s=b['metrics']['full_JF']-r['metrics']['full_JF'],qualified=r['qualified'],original_full_JF=r['metrics']['full_JF']))
  X=np.asarray(contexts);xc=X.mean(0);xs=np.maximum(X.std(0),[.5,.05,.05,.2,.2]);query={};aliases={};seen={}
  for tag in menu:
   key=canonical(lib[tag],phase)
   if key in seen:aliases[tag]=seen[key];continue
   seen[key]=tag;all_rr=[r for r in rows if canonical(lib[r['tag']],phase)==key];rr=[r for r in all_rr if r['group'] in training_groups];groups=sorted(set(r['group'] for r in rr));vals=[float(np.mean([r['gain_vs_B_N_s'] for r in rr if r['group']==g])) for g in groups];query[tag]=dict(predicted_gain_vs_B_N_s=float(np.mean(vals)),development_std_N_s=float(np.std(vals)),unique_parent_samples=len(groups),qualified_samples=sum(all(r['qualified'] for r in rr if r['group']==g) for g in groups),all_development_original_qualified=all(r['qualified'] for r in all_rr),additional_actual_feedback_groups=sorted(set(r['group'] for r in all_rr if r['group'] in additional_groups)),training_groups=groups)
  residuals=[]
  for r in rows:
   if r['group'] not in additional_groups:continue
   tag=aliases.get(r['tag'],r['tag']);residuals.append(r['gain_vs_B_N_s']-query[tag]['predicted_gain_vs_B_N_s'])
  offset=float(np.mean(residuals)) if residuals else 0.
  for entry in query.values():entry['predicted_gain_vs_B_N_s']+=offset
  phases[phase]=dict(unpaired_feedback_scope='updates common offset and uncertainty/domain only; preserves relative action ranking from fully paired menus',common_feedback_offset_N_s=offset,feedback_residuals_N_s=residuals,x_center=xc.tolist(),x_scale=xs.tolist(),train_x=((X-xc)/xs).tolist(),ood_limit=1.5,ranking=query,aliases=aliases,original_candidate_menu=menu,unique_candidate_menu=list(query),fallback_tag='COMPOSE',phase=phase,required_upstream_policy='COMPOSE' if phase=='RETURN' else 'ORIGINAL_B_PREFIX')
 usage=resource.getrusage(resource.RUSAGE_SELF)
 return dict(fit_resources=dict(wall_s=time.perf_counter()-started,cpu_user_s=usage.ru_utime-usage_start.ru_utime,cpu_system_s=usage.ru_stime-usage_start.ru_stime,peak_process_rss_kib=usage.ru_maxrss,new_native_steps=0),schema='v6.traditional.phase_library_proxy.v1',phases=phases,created_unix=time.time(),training_groups=sorted(set(sources)),training_mode='group-weighted empirical gain lookup; no state-conditioned learning where ranking variation is not established',future_execution_state_used=False,original_guard_and_admission_unchanged=True)
def query(model,phase,context):
 m=model['phases'][phase];x=np.array(context_vector(context));z=(x-m['x_center'])/m['x_scale'];distance=float(np.min(np.sqrt(np.mean((np.array(m['train_x'])-z)**2,axis=1))));rows=[dict(tag=t,**v) for t,v in m['ranking'].items()];allowed=[r for r in rows if r['all_development_original_qualified']];domain_ok=phase!='RETURN' or context.get('upstream_policy')=='COMPOSE';choice=max(allowed,key=lambda r:r['predicted_gain_vs_B_N_s'])['tag'] if allowed and domain_ok and distance<=m['ood_limit'] else None
 return dict(choice=choice,upstream_domain_match=domain_ok,rows=rows,aliases=m['aliases'],original_menu=m['original_candidate_menu'],unique_menu=m['unique_candidate_menu'],ood_distance=distance,ood_limit=m['ood_limit'],ood_fallback=distance>m['ood_limit'],uses_H_state=False,uses_candidate_physics=False,qualification='development coverage is not a certificate; original planner/admission/guard decide all actual writes')
def sequence(study,C):
 preparation_started=time.perf_counter()
 from acl2_shared import put,read
 path=P/C['frozen_proxy'];assert sha(path)==C['frozen_proxy_sha256'],'FROZEN_PRESTATE_PROXY_CHANGED'
 model=json.loads(path.read_text());context=read('audit/'+C['group']+'_FORK_CONTEXT.json');started=time.perf_counter();decision=query(model,C['fork_phase'],context);decision.update(created_unix=time.time(),prediction_wall_s=time.perf_counter()-started,context_parent_hash=context['parent_hash'],frozen_proxy_sha256=sha(path),before_any_offered_candidate_START=True,original_B_anchor_is_separately_paid=True,total_preselection_wall_s=time.perf_counter()-preparation_started)
 put('predictions/'+C['group']+'_PRESTATE_SCREEN.json',decision)
 yield next(a for a in C['actions'] if a['tag']=='B')
 if C.get('exhaustive_audit'):
  for tag in decision['unique_menu']:yield next(a for a in C['actions'] if a['tag']==tag)
 elif decision['choice'] is not None:
  chosen=next(a for a in C['actions'] if a['tag']==decision['choice']);yield chosen
