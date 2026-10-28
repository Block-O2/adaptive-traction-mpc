#!/usr/bin/env python3
"""Prediction-only sidecar. No scientific imports, fit, dispatch or outcome reads.

Main agent must review/freeze this file and MODEL.json before separately starting
one bounded watcher per group. The final WATCH_END is the admissibility authority.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,math,os,signal,sys,time

GROUPS={'CFH':'CFACTORH01','CFL':'CFACTORL01','CFACTORH01':'CFACTORH01','CFACTORL01':'CFACTORL01'}
SCHEMA='ihear.causal_human_context.v1.77d'
CAPTURE='parent request boundary BEFORE fork loop/candidate selection/control mutation'
K1='estimated_beta_k1_passive_stiffness';K2='estimated_beta_k2_passive_stiffness';G='estimated_geometry_thigh_length'
SOURCE_REL='source/v7_causal_context.py'
MAX_CONTEXT_BYTES=65536

GLOBAL_HARD_DEADLINE=1793073411.846771
class DeadlineExpired(RuntimeError):pass
class Deadline:
    """Reserve 100ms for best-effort NOT_TESTED sealing inside the hard bound.

    Existing real timer remains an earlier hard bound, never reset to its old
    full duration. If it expired, restore its handler and deliver that signal.
    """
    def __init__(self,timeout):
        if not 0.<timeout<=600.:raise ValueError('WATCH_TIMEOUT_OUT_OF_SCOPE')
        self.start_wall=time.time();self.start_mono=time.monotonic()
        self.old_handler=signal.getsignal(signal.SIGALRM)
        self.old_timer=signal.getitimer(signal.ITIMER_REAL)
        self.old_due=self.start_mono+self.old_timer[0] if self.old_timer[0]>0 else None
        duration=min(timeout,GLOBAL_HARD_DEADLINE-self.start_wall)
        if self.old_due is not None:duration=min(duration,self.old_timer[0])
        if duration<=.1:raise DeadlineExpired('NO_HARD_DEADLINE_RESERVE')
        self.hard_wall=self.start_wall+duration;self.hard_mono=self.start_mono+duration
        self.compute_wall=self.hard_wall-.1;self.compute_mono=self.hard_mono-.1
        self.cleanup=False;self.closed=False
        signal.signal(signal.SIGALRM,self._alarm)
        signal.setitimer(signal.ITIMER_REAL,max(.000001,duration-.1))
    def _alarm(self,*_):raise DeadlineExpired('HARD_CLEANUP_ALARM' if self.cleanup else 'COMPUTE_ALARM')
    def check(self,stage,hard=False):
        wall=self.hard_wall if hard else self.compute_wall
        mono=self.hard_mono if hard else self.compute_mono
        if time.time()>=wall or time.monotonic()>=mono:raise DeadlineExpired(stage)
    def begin_cleanup(self):
        self.cleanup=True
        remaining=min(self.hard_wall-time.time(),self.hard_mono-time.monotonic())
        if remaining<=0:raise DeadlineExpired('NO_CLEANUP_TIME')
        signal.setitimer(signal.ITIMER_REAL,max(.000001,remaining))
    def close(self):
        if self.closed:return
        self.closed=True;signal.setitimer(signal.ITIMER_REAL,0.)
        signal.signal(signal.SIGALRM,self.old_handler)
        if self.old_due is not None:
            remaining=self.old_due-time.monotonic();interval=self.old_timer[1]
            if remaining>0:signal.setitimer(signal.ITIMER_REAL,remaining,interval)
            else:
                if interval>0:
                    next_delay=interval-((-remaining)%interval)
                    signal.setitimer(signal.ITIMER_REAL,next_delay,interval)
                signal.raise_signal(signal.SIGALRM)
        elif self.old_timer[1]:signal.setitimer(signal.ITIMER_REAL,0.,self.old_timer[1])
    def record(self):return dict(hard_wall=self.hard_wall,hard_mono=self.hard_mono,compute_wall=self.compute_wall,compute_mono=self.compute_mono,cleanup_reserve_s=.1,old_timer=self.old_timer)

def checked_publish(path,value,deadline,stage):
    deadline.check(stage+'_PRE')
    atomic_create(path,value)
    deadline.check(stage+'_POST')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def process():
 p=Path('/proc/self/stat').read_text();return {'pid':os.getpid(),'start_ticks':int(p[p.rfind(')')+2:].split()[19])}
def atomic_create(path,value):
 """Immutable atomic publication on the same filesystem, refusing overwrite."""
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.tmp.'+str(os.getpid())+'.'+str(time.time_ns()))
 try:
  with tmp.open('x') as f:
   f.write(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
  os.link(tmp,path)  # Atomic create-if-absent, never os.replace an existing result.
 finally:
  if tmp.exists():tmp.unlink()

def finite(x):return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def validate_context(context,feature_names):
 """Validate only three causal inputs at OUT0; never promote the full 77D."""
 errors=[]
 def require(v,why):
  if not v:errors.append(why)
 payload={k:v for k,v in context.items() if k!='causal_payload_sha256'}
 try:require(context.get('causal_payload_sha256')==digest(payload),'PAYLOAD_HASH')
 except (ValueError,TypeError):errors.append('NONJSON_OR_NONFINITE_PAYLOAD')
 require(context.get('schema')==SCHEMA,'SCHEMA')
 names=context.get('feature_names',[]);values=context.get('features',[])
 require(names==feature_names and len(names)==len(set(names))==77,'FEATURE_SCHEMA')
 require(len(values)==77 and context.get('feature_dimension')==77,'FEATURE_DIMENSION')
 fmap=dict(zip(names,values))
 require(context.get('phase')=='OUTBOUND','NOT_OUTBOUND')
 require(finite(context.get('task_s')) and abs(context['task_s'])<=1e-9,'NOT_TASK_ZERO')
 require(context.get('capture_position')==CAPTURE,'NOT_PREFORK_PARENT_POSITION')
 require(context.get('hidden_or_future_inputs_used') is False,'HIDDEN_OR_FUTURE_FLAG')
 require(context.get('model_prediction_or_observe_calls')==0,'CAPTURE_EXTRA_CALLS')
 require(context.get('model_vector_valid') is False,'FULL77D_EXPECTED_INVALID_NOT_REPAIRED')
 require(context.get('causality_errors')==['capture_is_not_registered_OUT1_boundary'],'UNEXPECTED_CAUSALITY_ERRORS')
 for name,expected in [('decision_slot',0.),('task_elapsed',0.),('phase_elapsed',0.),('phase_OUTBOUND',1.),('phase_HOLD',0.),('phase_RETURN',0.),('task_contract_remaining',30.)]:
  value=fmap.get(name);require(finite(value) and abs(value-expected)<=1e-9,'OUT0_METADATA:'+name)
 for name in [K1,K2,G]:require(finite(fmap.get(name)) and fmap[name]>0,'REQUIRED_FEATURE:'+name)
 q=context.get('quality',{})
 for name in ['observation_age','interface_age']:
  require(finite(q.get(name)) and q[name]>=-1e-9,'QUALITY_AGE:'+name)
 if finite(q.get('observation_age')) and finite(q.get('interface_age')):require(abs(q['observation_age']-q['interface_age'])<=1e-9,'SENSOR_ALIGNMENT')
 require(finite(fmap.get('request_source_age')) and fmap['request_source_age']>=-1e-9,'REQUEST_IN_FUTURE')
 require(q.get('geometry_fit_accepted')==1.,'GEOMETRY_FIT_NOT_ACCEPTED')
 require(finite(q.get('geometry_fit_sample_count')) and q['geometry_fit_sample_count']>0,'GEOMETRY_SAMPLES')
 require(finite(q.get('dynamics_sample_count')) and q['dynamics_sample_count']>0,'DYNAMICS_SAMPLES')
 require(finite(q.get('accepted_beta_updates')) and q['accepted_beta_updates']>0,'NO_ESTIMATED_BETA_UPDATES')
 warning_keys=['last_attempt_bound_hit','last_attempt_rate_limit_hit','excluded_soft_limit_sample_count','coefficient_projection_count','observed_output_cap_count']
 warnings={k:q.get(k) for k in warning_keys if q.get(k) not in (None,0.,False)}
 warnings.update({k:v for k,v in q.items() if k.startswith('last_attempt_conditional_frozen_') and v not in (None,0.,False)})
 result={'status':'VALID_FOR_TWO_STUMP_INPUTS_ONLY' if not errors else 'INVALID_FOR_STUMP_INPUTS','errors':errors,'full77D_model_vector_valid_original':context.get('model_vector_valid'),'full77D_status':'INVALID_UNCHANGED','quality':q,'quality_missing':context.get('quality_missing'),'QA_warnings':warnings,'missing_model_groups_original':context.get('missing_model_groups'),'causality_errors_original':context.get('causality_errors'),'hidden_or_future_inputs_used':False,'inputs':None}
 if not errors:result['inputs']={'K_stump':(fmap[K1]+fmap[K2])/2.,'geometry_stump':fmap[G]}
 return result

def predict_one(model,value):
 if not finite(value):raise ValueError('NONFINITE_STUMP_INPUT')
 polarity=model['polarity']
 if polarity=='gt_positive':return int(value>model['threshold'])
 if polarity=='le_positive':return int(value<=model['threshold'])
 raise ValueError('UNKNOWN_POLARITY')
def recommendations(model,validation):
 if validation['status']!='VALID_FOR_TWO_STUMP_INPUTS_ONLY':raise ValueError('INVALID_SUBSET')
 out={}
 for name in ['K_stump','geometry_stump']:
  label=predict_one(model['models'][name],validation['inputs'][name]);out[name]={'predicted_qualified_benefit_label':label,'suggested_action':'EARLY_H150' if label else 'B'}
 out['always_B']={'suggested_action':'B'};out['always_EARLY_H150']={'suggested_action':'EARLY_H150'}
 return out

def candidate_ends(ledger,group):
 """Parse only this group's END identity/time; never read a cost/result file."""
 rows=[];needle=('"id": "'+group+'_').encode()
 if not Path(ledger).exists():return rows
 with Path(ledger).open('rb') as f:
  for line in f:
   if needle not in line and ('"id":"'+group+'_').encode() not in line:continue
   if not line.endswith(b'\n'):continue
   event=json.loads(line)
   ident=event.get('id','')
   if event.get('event')=='END' and ident.startswith(group+'_') and ident!=group+'_parent':rows.append({k:event.get(k) for k in ['event','id','unix','pid','start_ticks']})
 return rows

def load_model(path,expected_sha):
 if sha(path)!=expected_sha:raise ValueError('MODEL_SHA_CHANGED')
 m=json.loads(Path(path).read_text())
 if m.get('schema')!='ihear.two_causal_stumps.v1' or m.get('simple_stump_fits')!=2:raise ValueError('MODEL_IDENTITY_OR_FIT_COUNT')
 if m.get('training_groups')!=['EARLYN01','EARLYL01','EARLYH01']:raise ValueError('TRAINING_GROUPS_CHANGED')
 if set(m.get('models',{}))!={'K_stump','geometry_stump'}:raise ValueError('MODEL_MENU_CHANGED')
 return m

def watch(args):
 deadline=Deadline(args.timeout_s)
 group=GROUPS[args.group];package=Path(args.package).resolve();out=Path(args.output_dir).resolve()/group
 try:
  out.mkdir(parents=True,exist_ok=True)
  start=time.time();mono=time.monotonic();identity=process();source_sha=sha(__file__)
  deadline.check('INITIALIZATION')
  atomic_create(out/'WATCH_START.json',dict(**identity,started_unix=start,source_sha256=source_sha,expected_source_sha256=args.watcher_sha256,expected_model_sha256=args.model_sha256,group=group,timeout_s=args.timeout_s,deadline=deadline.record(),scope='prediction only; no control/guard/menu mutation or outcome reads'))
 except BaseException:
  deadline.close();raise
 end={'status':'NOT_TESTED','prediction_admissible':False,'reason':None};provisional=False
 contextpath=package/'history'/(group+'_PREFORK_CAUSAL_CONTEXT.json');ledger=package/'runtime/ATTEMPTS.jsonl'
 try:
  if source_sha!=args.watcher_sha256:raise ValueError('WATCHER_SOURCE_SHA_CHANGED')
  model=load_model(args.model,args.model_sha256)
  deadline.check('MODEL_LOAD')
  if model['global_hard_deadline_unix']!=GLOBAL_HARD_DEADLINE:raise ValueError('GLOBAL_DEADLINE_CHANGED')
  if model['watcher_source_sha256']!=source_sha:raise ValueError('MODEL_WATCHER_SOURCE_BINDING')
  if sha(package/SOURCE_REL)!=model['context_source_sha256']:raise ValueError('CONTEXT_PRODUCER_SOURCE_CHANGED')
  if not 0.<args.timeout_s<=600.:raise ValueError('WATCH_TIMEOUT_OUT_OF_SCOPE')
  stop=min(start+args.timeout_s,model['global_hard_deadline_unix'])
  if contextpath.exists():end['reason']='CONTEXT_ALREADY_EXISTS_AT_WATCH_START';return
  while True:
   late=candidate_ends(ledger,group)
   if late:end.update(reason='CANDIDATE_END_BEFORE_PREDICTION',candidate_END_identity_only=late);return
   deadline.check('WAIT_LOOP')
   if contextpath.exists():break
   time.sleep(.05)
  if contextpath.resolve()!=contextpath or contextpath.stat().st_size>MAX_CONTEXT_BYTES:raise ValueError('CONTEXT_PATH_OR_SIZE')
  deadline.check('CONTEXT_PRE')
  raw=contextpath.read_bytes();context=json.loads(raw);context_sha=hashlib.sha256(raw).hexdigest();validation=validate_context(context,model['feature_names'])
  deadline.check('VALIDATION_POST')
  if validation['status']!='VALID_FOR_TWO_STUMP_INPUTS_ONLY':
   end.update(reason='INVALID_PURPOSE_SPECIFIC_SUBSET',validation=validation,input_context_sha256=context_sha);return
  late=candidate_ends(ledger,group)
  if late:end.update(reason='CANDIDATE_END_DURING_VALIDATION',candidate_END_identity_only=late,input_context_sha256=context_sha);return
  if sha(args.model)!=args.model_sha256 or sha(__file__)!=args.watcher_sha256 or sha(contextpath)!=context_sha:raise ValueError('PREDICTION_INPUT_OR_SOURCE_CHANGED')
  deadline.check('HASH_POST_PREPUBLICATION')
  prediction=recommendations(model,validation)
  deadline.check('PREDICTION_POST')
  payload=dict(schema='ihear.prospective_stump_prediction.v1',process=identity,group=group,prepared_unix=time.time(),watch_started_unix=start,source_sha256=source_sha,model_sha256=args.model_sha256,context_source_sha256=model['context_source_sha256'],input_context_sha256=context_sha,causal_payload_sha256=context['causal_payload_sha256'],validation=validation,predictions=prediction,prospective_eligibility='PENDING_POSTPUBLICATION_END_CHECK',deployment=False,menu_changed=False,physics_saved=0,neural_calls=0,JM_not_predicted_or_scalarized=True)
  provisional=True
  checked_publish(out/'PREDICTION.json',payload,deadline,'PREDICTION_PUBLICATION');published=time.time()
  deadline.check('PREDICTION_PUBLISHED')
  # Sidecar cannot lock the worker ledger. Explicitly invalidate any publication
  # race, retaining evidence and never rerunning/backfilling the prediction.
  late=candidate_ends(ledger,group)
  deadline.check('POSTPUBLICATION_LEDGER')
  if late:
   end.update(reason='CANDIDATE_END_AT_POSTPUBLICATION_CHECK',candidate_END_identity_only=late,provisional_prediction_retained_but_not_admissible=True,published_unix=published);return
  deadline.check('FINAL_ADMISSIBILITY')
  end.update(status='PREDICTION_SEALED_PENDING_MAIN_COMMIT_AUDIT',prediction_admissible=False,local_deadline_checks_passed=True,requires_main_commit_time_audit=True,reason='LOCAL_CHECKS_PASS_MAIN_AUDIT_REQUIRED',published_unix=published,prediction_sha256=sha(out/'PREDICTION.json'),candidate_END_absent_at_postpublication_check=True,input_context_sha256=context_sha,model_sha256=args.model_sha256,source_sha256=source_sha)
 except BaseException as error:
  end.update(status='NOT_TESTED',prediction_admissible=False,local_deadline_checks_passed=False,reason=type(error).__name__+':'+str(error),provisional_prediction_retained_but_not_admissible=provisional)
 finally:
  try:
   if end.get('local_deadline_checks_passed'):
    try:deadline.check('FINAL_END_PREPARATION')
    except DeadlineExpired as error:end.update(status='NOT_TESTED',prediction_admissible=False,local_deadline_checks_passed=False,reason='FINAL_DEADLINE:'+str(error))
   deadline.begin_cleanup()
   end.update(process=identity,ended_unix=time.time(),wall_s=time.monotonic()-mono,group=group,deadline=deadline.record(),neural_calls=0,environment_calls=0,physical_START=0,training_fits=0)
   # Status files are immutable. An invalidation marker overrides a rare
   # deadline race while the final END itself is being published.
   atomic_create(out/'WATCH_END.json',end)
   deadline.check('FINAL_END_COMMIT',hard=True)
   if end.get('local_deadline_checks_passed'):deadline.check('FINAL_ADMISSIBILITY_POSTCOMMIT')
  except DeadlineExpired as error:
   end.update(status='NOT_TESTED',prediction_admissible=False,local_deadline_checks_passed=False,reason='FINAL_SEAL_DEADLINE:'+str(error),provisional_prediction_retained_but_not_admissible=provisional)
   try:
    deadline.begin_cleanup()
    if not (out/'WATCH_END.json').exists():atomic_create(out/'WATCH_END.json',end)
    else:atomic_create(out/'WATCH_INVALIDATED.json',end)
   except BaseException:pass  # Missing END/invalidation requires main audit; never assume PASS.
  finally:deadline.close()

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--group',choices=sorted(GROUPS),required=True);p.add_argument('--package',required=True);p.add_argument('--model',required=True);p.add_argument('--model-sha256',required=True);p.add_argument('--watcher-sha256',required=True);p.add_argument('--output-dir',required=True);p.add_argument('--timeout-s',type=float,default=600.)
 a=p.parse_args();watch(a)
if __name__=='__main__':main()
