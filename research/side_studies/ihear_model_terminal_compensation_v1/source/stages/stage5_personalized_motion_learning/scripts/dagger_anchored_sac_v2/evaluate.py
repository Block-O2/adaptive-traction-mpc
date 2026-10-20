from common import *
def run(request):
 random.seed(request['seed']);np.random.seed(request['seed']);torch.manual_seed(request['seed'])
 a=actor();a.load_state_dict(torch.load(request['actor'],map_location='cpu',weights_only=False));a.eval()
 case,options=load_case_options();env=SACExpertEnv(O/request['name'],case,options,.02,request['scope'],True);data={k:[] for k in ('observations','actions','executed_actions','next_observations','rewards','terminated','truncated','phase')}
 try:
  obs,info=env.reset(seed=request.get('initial_condition_seed',read('PREREGISTRATION.json')['initial_condition_seed']));initial_hash=env.model_hash
  assert initial_hash==read('BASELINE_LOCK.json')['frozen_model_hash']
  with torch.no_grad():
   while True:
    ac,_=a.predict(obs,deterministic=not request.get('stochastic',False));before=obs.copy();ph=info['phase']
    obs,reward,term,trunc,info=env.step(ac)
    for k,v in dict(observations=before,actions=ac,executed_actions=np.asarray(env.last_row['executed'],np.float32),next_observations=obs.copy(),rewards=reward,terminated=term,truncated=trunc,phase=ph).items():data[k].append(v)
    if term or trunc:break
  row=metric(env,request['name'],request['scope']);path=env.episode_dir/'TRANSITIONS.npz';np.savez_compressed(path,**{k:np.asarray(v) for k,v in data.items()})
  row.update(transitions=str(path),steps=len(data['actions']),stochastic=request.get('stochastic',False),evaluation_rng_seed=request['seed'],process_pid=os.getpid(),model_hash=initial_hash)
  compact_archive(env);save(request['result'],row)
  print(json.dumps(clean({k:row[k] for k in ('name','scope','valid','J_F','duration_s','termination','steps')})),flush=True)
 finally:env.close()
if __name__=='__main__':run(json.loads(Path(sys.argv[1]).read_text()))
