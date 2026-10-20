from common import *
class Interface:
 def __init__(self,action=None):self.action=action or {};self.child=None;self.rows=[]
 def decision_boundary(self,b):pass
 def boundary(self,b):
  r=b['reference'];self.rows.append([b['task_state'].phase.value,float(b['physical_now']-b['task_start_time']),*r.q_rad,*r.dq_rad_s,*r.ddq_rad_s2])
 def finish(self,env,metric):
  np.savez_compressed(env.episode_dir/'native_reference.npz',phase=[r[0] for r in self.rows],data=np.asarray([r[1:] for r in self.rows]))
def artifacts(folder):
 p=folder/'runtime_artifacts.json'
 return json.loads(p.read_text() if p.exists() else gzip.open(str(p)+'.gz','rt').read())
def zero(name='zero_v2'):
 interface=Interface();m=run(name,interface)
 a=np.load(S/'results/coordination_research_interface_v1/B_original/trace.npz');b=np.load(O/name/'trace.npz')
 errors={};mismatch=[]
 for k in a.files:
  if k not in b.files or a[k].shape!=b[k].shape:mismatch.append(k);continue
  if a[k].dtype.kind in 'fiu':
   if not np.array_equal(np.isnan(a[k]),np.isnan(b[k])):mismatch.append(k)
   f=np.isfinite(a[k])&np.isfinite(b[k]);errors[k]=float(np.max(np.abs(a[k][f]-b[k][f]))) if np.any(f) else 0.
  elif not np.array_equal(a[k],b[k]):mismatch.append(k)
 z=np.load(W.parent/'coordination_research_interface_v1/output/B_TAPE.npz');r=np.load(O/name/'native_reference.npz')
 ref=np.column_stack([z['t'],z['q'],z['v'],z['a']]);referror=float(np.max(np.abs(ref-r['data'])))
 base=json.loads((W.parent/'coordination_research_interface_v1/output/B_original.json').read_text())
 gate=dict(pass_=not mismatch and all(v<=1e-10 for v in errors.values()) and referror<=1e-10 and abs(m['J_F']-base['J_F'])<=1e-6 and m['valid'] and m['matched_eligible'],mismatch=mismatch,array_errors=errors,reference_error=referror,J_F_error=abs(m['J_F']-base['J_F']),metric=m)
 save(name+'_GATE.json',gate);assert gate['pass_'],'ZERO_GATE_STOP'
 return gate
def pattern(kind,a):
 hip=[[0,0],[.15,a],[.8,a],[1,0]]
 knee=[[x,-y] for x,y in hip]
 catch=[[0,0],[.2,a],[.5,a],[.65,0],[1,0]]
 reverse=[[0,0],[.2,a],[.4,a],[.65,-a],[.85,-a],[1,0]]
 graph={'hip':hip,'knee':knee,'catchup':catch,'reversal':reverse,'independent':hip}[kind]
 return {'OUTBOUND':graph,'RETURN':knee if kind=='independent' else graph}
def audit(name,m):
 art=json.loads((O/name/'summary.json').read_text());events=[]
 def walk(x):
  if isinstance(x,dict):
   if 'coordination_residual_v2' in x:events.append(x['coordination_residual_v2'])
   for v in x.values():walk(v)
  elif isinstance(x,list):
   for v in x:walk(v)
 walk(art)
 unique={json.dumps(x,sort_keys=True):x for x in events};events=list(unique.values())
 accepted=[x for x in events if x['status']=='ACCEPTED']
 decisions=art['decisions'];activated=[d for d in decisions if d.get('plan_activated') and d.get('selection_mode')=='native_residual_v2_ACCEPTED']
 base=np.load(O/'zero_v2/native_reference.npz');ref=np.load(O/name/'native_reference.npz')
 different=base['data'].shape!=ref['data'].shape or not np.array_equal(base['data'][:,1:],ref['data'][:,1:])
 row=dict(metric=m,events=events,accepted=len(accepted),activated=len(activated),reference_differs=different,rejected=len(events)-len(accepted),common_error=max([abs(x['common_error']) for x in events] or [0.]),pass_=m['valid'] and m['matched_eligible'] and len(activated)>0 and different)
 save(name+'_AUDIT.json',row);return row
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('mode');p.add_argument('--kind');p.add_argument('--amplitude',type=float,default=.01);p.add_argument('--name');args=p.parse_args()
 if args.mode=='zero':zero(args.name or 'zero_v2')
 else:
  name=args.name or args.kind+'_'+str(args.amplitude);a=pattern(args.kind,args.amplitude);save(name+'_ACTION.json',a);m=run(name,Interface(a));row=audit(name,m);print(json.dumps(dict(name=name,accepted=row['accepted'],pass_=row['pass_'])),flush=True)
