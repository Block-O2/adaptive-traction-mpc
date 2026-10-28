#!/usr/bin/env python3
"""Finite offline identity audit. No simulator/model/control imports or dispatch.

inventory: approved historical snapshots only, optional bounded representative NPZ reads.
postrun: main-agent invocation only AFTER its validation freeze and physical execution.
The inventory mode refuses new PFXV/short-segment paths in the current v7 package.
"""
from pathlib import Path
import argparse,copy,hashlib,json,os,time,resource
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
V7='autonomous_learning_smoothness_v7'
HISTORICAL=['learning_guided_motion_improvement_v1','autonomous_coordination_learning_v2','representation_execution_v3','constraint_geometry_learning_v4','smoothness_critic_research_v5','smoothness_critic_integration_v6']
V7_ALLOWED=['DEVRT01','DEVRT02','DEVRT03','DEVRC01','DEVRC02','DEVPC01','DEVPC02','HUMANLS01','HUMANHS01','H150L01','H150H01','H150N01','LSREP01','HSAPP01','LSTIM01','EARLYH01','EARLYN01','EARLYL01']

def sha(f):
 h=hashlib.sha256()
 with Path(f).open('rb') as s:
  for b in iter(lambda:s.read(2**20),b''):h.update(b)
 return h.hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(f):return json.loads(Path(f).read_text())
def atomic(f,x):
 f=Path(f);assert not f.exists(),'REFUSE_OVERWRITE:'+str(f);f.parent.mkdir(parents=True,exist_ok=True)
 t=f.with_name(f.name+'.tmp.'+str(os.getpid()));t.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(t,f)
def process():
 s=Path('/proc/self/stat').read_text();return {'pid':os.getpid(),'start_ticks':int(s[s.rfind(')')+2:].split()[19])}
def allowed_v7(ident):return any(ident.startswith(g+'_') for g in V7_ALLOWED)
def array_node(value):
 return value if isinstance(value,dict) and set(['dtype','shape','sha256'])<=set(value) else None

def extract(snapshot,package,ident):
 s=read(snapshot);m=s.get('manifest',{});rfile=package/'attempts'/(ident+'_RESULT.json');r=read(rfile) if rfile.exists() else {}
 branch=r.get('branch') or {};fork=branch.get('physical_time_s',m.get('task_last_physics_time'));args=m.get('arguments',{})
 integ=array_node(m.get('native_integration'));causal=array_node(args.get('current_deployable_state'));ref=array_node(args.get('current_reference_state'))
 group_candidates=[f.stem for f in (package/'experiments').glob('*.json') if ident.startswith(f.stem+'_')];group=max(group_candidates,key=len) if group_candidates else None
 condition=None;case=None;config_hash=None
 if group:
  cf=package/'experiments'/(group+'.json');config=read(cf);condition=config.get('condition');case=config.get('case_path');config_hash=sha(cf)
 return {'package':package.name,'id':ident,'group':group,'snapshot':str(snapshot),'snapshot_sha256':sha(snapshot),'native_state_mask':s.get('native_state_mask'),'native_state_count':s.get('native_state_count'),'native_integration':integ,'causal_current_deployable_array':causal,'request_reference_array':ref,'full_hash':s.get('hash'),'native_hash_name_is_full_manifest_not_integration':s.get('native_hash'),'full_hash_has_extra_77D_payload':s.get('causal_context_sha256') is not None,'causal_context_sha256':s.get('causal_context_sha256'),'fork_physics_s':fork,'task_start_s':m.get('task_start_time'),'phase':m.get('task_state',{}).get('state',{}).get('phase'),'result':str(rfile) if rfile.exists() else None,'result_sha256':sha(rfile) if rfile.exists() else None,'complete':r.get('complete'),'qualified':r.get('qualified'),'trace':str(package/'runtime/source/results'/ident/'trace.npz'),'condition_for_audit_only':condition,'case_path_for_audit_only':case,'config_sha256_for_audit_only':config_hash,'exposure_reason':'Historical snapshot evidence including incomplete/failed branches; no success filter'}

def trace_projection(path,fork):
 import numpy as np
 path=Path(path);assert path.is_file(),'MISSING_TRACE';assert fork is not None,'MISSING_FORK_TIME'
 with np.load(path,allow_pickle=False) as z:
  keys=['time_s','evaluation_only_human_state_rad_rad_s','cr12_actuator_command_nm'];assert all(k in z.files for k in keys),'INCOMPATIBLE_TRACE_SCHEMA'
  t=z['time_s'];mask=t<float(fork)-1e-9;assert mask.any(),'EMPTY_STRICT_PREFORK_TRACE';h=hashlib.sha256();schema=[]
  for k in keys:
   v=np.ascontiguousarray(z[k][mask]);h.update(k.encode());h.update(str(v.dtype).encode());h.update(str(v.shape).encode());h.update(v.tobytes());schema.append({'key':k,'dtype':str(v.dtype),'shape':list(v.shape)})
  def separate_digest(named_keys, include_time=True):
   hh=hashlib.sha256()
   for kk in (['time_s'] if include_time else [])+named_keys:
    vv=np.ascontiguousarray(z[kk][mask]);hh.update(kk.encode());hh.update(str(vv.dtype).encode());hh.update(str(vv.shape).encode());hh.update(vv.tobytes())
   return hh.hexdigest()
  physical_only=separate_digest(['evaluation_only_human_state_rad_rad_s']);physical_values=separate_digest(['evaluation_only_human_state_rad_rad_s'],False);command_only=separate_digest(['cr12_actuator_command_nm'])
  physical=z[keys[1]][mask];causal=z['estimated_human_state_rad_rad_s'][mask] if 'estimated_human_state_rad_rad_s' in z.files else None
  return {'schema':'ihear.strict_prefork_trace.time_human_qdq_command.v1','sha256':h.hexdigest(),'actual_human_trace_sha256':physical_only,'actual_human_values_sha256':physical_values,'command_trace_sha256':command_only,'pure_physical_scope':'Actual Human q/dq projection only; no command/label/host/ref in actual_human hashes, not full robot/cuff native history','rows':int(mask.sum()),'fork_physics_s':float(fork),'first_time_s':float(t[mask][0]),'last_time_s':float(t[mask][-1]),'strict_before_rule':'time_s < fork_physics_s - 1e-9','array_schema':schema,'last_prefork_physical_human_qdq':physical[-1].tolist(),'last_prefork_estimated_human_qdq':None if causal is None else causal[-1].tolist(),'last_prefork_is_not_exact_fork_observation':True,'trace_sha256':sha(path)}

def inventory(a):
 root=Path(a.workspace).resolve();start=read(a.start);begin=time.time();pid=process();rows=[];errors=[];excluded=[]
 atomic(str(a.out)+'.START.json',dict(process=pid,start_unix=begin,source_sha256=sha(Path(__file__)),start_manifest_sha256=sha(a.start),mode='HISTORICAL_INVENTORY_NO_NEW_PREFIX_DATA'))
 for pkg in HISTORICAL+[V7]:
  q=root/pkg
  for f in sorted((q/'runtime/reports').glob('*_SNAPSHOT.json')):
   ident=f.name[:-len('_SNAPSHOT.json')]
   if pkg==V7 and (not allowed_v7(ident) or f.stat().st_mtime>start['start_unix']):excluded.append({'path':str(f),'reason':'NOT_IN_FROZEN_KNOWN_V7_ALLOWLIST_OR_AFTER_REVIEW_CUTOFF'});continue
   assert time.time()<min(start['start_unix']+start['budget_wall_s'],start['deadline_unix'])-30,'REVIEW_DEADLINE'
   try:rows.append(extract(f,q,ident))
   except Exception as e:errors.append({'path':str(f),'error':type(e).__name__+': '+str(e)})
 # A trace cache includes the causal array and phase/time, never seed/config alone.
 groups={}
 for r in rows:
  k=digest({'native':r['native_integration'],'causal':r['causal_current_deployable_array'],'reference':r['request_reference_array'],'phase':r['phase'],'fork':r['fork_physics_s']});groups.setdefault(k,[]).append(r)
 for key,rr in groups.items():
  for r in rr:
   projection=None;failures=[]
   if a.with_traces and Path(r['trace']).exists():
    assert time.time()<min(start['start_unix']+start['budget_wall_s'],start['deadline_unix'])-30,'REVIEW_DEADLINE'
    try:
     projection=trace_projection(r['trace'],r['fork_physics_s']);projection['representative_id']=r['package']+'/'+r['id'];projection['representative_only_not_proof_every_group_history_equal']=False
    except Exception as e:failures.append({'id':r['package']+'/'+r['id'],'error':str(e)})
   r['conservative_endpoint_bucket']=key;r['representative_prefork_projection']=projection;r['own_prefork_projection']=projection;r['trace_projection_failures']=failures
 result={'branch':'PREVALIDATION_EXPOSURE_INVENTORY_V2','mode':'HISTORICAL_INVENTORY','created_unix':time.time(),'cutoff_unix':start['start_unix'],'process':pid,'source_sha256':sha(Path(__file__)),'start_manifest_sha256':sha(a.start),'snapshot_rows':rows,'conservative_endpoint_buckets':len(groups),'errors':errors,'excluded_without_opening':excluded,'registered_new_validation_data_opened':False,'new_physics':0,'model_calls':0,'training':0,'wall_s':time.time()-begin,'proof_limits':['Native integration hash is not complete causal controller identity','Each available compatible trace is fingerprinted separately; missing/incompatible historical trace remains unproven','No PFXV or new short-segment data opened','Scenario source inclusion is not proof of execution/exposure','Inventory covers seven snapshot-bearing study packages; other raw histories without snapshots remain a separate exposure-audit limit']}
 atomic(a.out,result);print(json.dumps({'snapshots':len(rows),'endpoint_buckets':len(groups),'native_states':len({r['native_integration']['sha256'] for r in rows if r['native_integration']}),'individually_verified_prefork_traces':sum(1 for r in rows if r['own_prefork_projection']),'errors':len(errors),'wall_s':result['wall_s'],'pid':pid['pid'],'start_ticks':pid['start_ticks']}))

def postrun(a):
 # Do not call this mode before main freezes menu/model and executes the registered case.
 inv=read(a.inventory);q=Path(a.package).resolve();r=extract(Path(a.snapshot),q,a.id);r['own_prefork_projection']=trace_projection(r['trace'],r['fork_physics_s']);pairs=[]
 for k in inv['snapshot_rows']:
  ni=r['native_integration'];ki=k['native_integration'];cs=r['causal_current_deployable_array'];ks=k['causal_current_deployable_array'];tp=k.get('representative_prefork_projection')
  pairs.append({'known':k['package']+'/'+k['id'],'native_schema_comparable':ni is not None and ki is not None and ni['dtype']==ki['dtype'] and ni['shape']==ki['shape'] and r['native_state_mask']==k['native_state_mask'],'native_integration_equal':None if ni is None or ki is None else ni==ki,'causal4_schema_comparable':cs is not None and ks is not None and cs['dtype']==ks['dtype'] and cs['shape']==ks['shape'],'causal_current4_equal':None if cs is None or ks is None or cs['dtype']!=ks['dtype'] or cs['shape']!=ks['shape'] else cs==ks,'prefork_trace_equal_to_known_representative':None if tp is None else r['own_prefork_projection']['actual_human_trace_sha256']==tp['actual_human_trace_sha256'],'mixed_state_command_trace_equal':None if tp is None else r['own_prefork_projection']['sha256']==tp['sha256'],'pure_human_values_equal':None if tp is None else r['own_prefork_projection']['actual_human_values_sha256']==tp['actual_human_values_sha256'],'last_strict_prefork_actual_human_qdq_max_abs_delta':None if tp is None else max(abs(x-y) for x,y in zip(r['own_prefork_projection']['last_prefork_physical_human_qdq'],tp['last_prefork_physical_human_qdq'])),'known_trace_is_representative_only':tp is not None and tp.get('representative_id')!=k['package']+'/'+k['id']})
 native_alias=[p['known'] for p in pairs if p['native_integration_equal'] is True];prefix_alias=[p['known'] for p in pairs if p['prefork_trace_equal_to_known_representative'] is True];causal_alias=[p['known'] for p in pairs if p['causal_current4_equal'] is True]
 result={'mode':'POSTRUN_IDENTITY_FILTER_ONLY','created_unix':time.time(),'process':process(),'source_sha256':sha(Path(__file__)),'inventory_sha256':sha(a.inventory),'candidate':r,'comparisons':pairs,'native_aliases':native_alias,'prefork_trace_aliases':prefix_alias,'common_causal4_alias_or_inconclusive_full77':causal_alias,'native_differs_from_every_inventory_row':all(p['native_schema_comparable'] and p['native_integration_equal'] is False for p in pairs),'common_causal4_differs_from_every_inventory_row':all(p['causal4_schema_comparable'] and p['causal_current4_equal'] is False for p in pairs),'prefix_comparison_complete_per_known_history':all(p['prefork_trace_equal_to_known_representative'] is not None and not p['known_trace_is_representative_only'] for p in pairs),'does_not_authorize_independence_PASS':True,'notes':['A fullhash difference caused by 77D payload/host/process address is not physical independence','A matching projected causal4 does not prove complete controller alias; it prevents claiming all-history full77 novelty from this projection alone','No menu/model freeze or physics dispatch is performed','Native/end-point differences are not statistical independence or cross-patient validation']}
 atomic(a.out,result);print(json.dumps({'native_aliases':len(native_alias),'prefix_aliases':len(prefix_alias),'causal4_matches':len(causal_alias),'output':a.out}))

if __name__=='__main__':
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
 i=sub.add_parser('inventory');i.add_argument('--workspace',required=True);i.add_argument('--start',required=True);i.add_argument('--out',required=True);i.add_argument('--with-traces',action='store_true')
 c=sub.add_parser('postrun');c.add_argument('--inventory',required=True);c.add_argument('--package',required=True);c.add_argument('--snapshot',required=True);c.add_argument('--id',required=True);c.add_argument('--out',required=True)
 args=parser.parse_args();inventory(args) if args.mode=='inventory' else postrun(args)
