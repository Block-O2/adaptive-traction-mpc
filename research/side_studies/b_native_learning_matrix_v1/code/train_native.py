"""Bounded direct Q/G fitting in a separate process; never owns MuJoCo."""
from task_bootstrap import *
import os,resource
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
def main():
 start=time.time();version=sys.argv[1] if len(sys.argv)>1 else 'v1';seed=int(sys.argv[2]) if len(sys.argv)>2 else 2026100611
 target=STUDY/'weights'/f'{version}_seed{seed}';target.mkdir(exist_ok=False)
 records=[];source_hashes={}
 for p in sorted((STUDY/'output').glob('*_DATA.json')):
  r=json.loads(p.read_text())
  if r.get('split') not in ('train','dev') or not r['metric']['valid'] or r['metric']['status']!='COMPLETE':continue
  records.append(r);source_hashes[str(p)]=sha(p)
 assert records,'NO_VALID_DATA'
 # Causal near-duplicate keys omit candidate U; all same-state branches stay together.
 def key(x):return np.round(np.asarray(x,np.float32),4).tobytes()
 normal=json.loads((STUDY/'output/003_zero_interface_retry1_DECISIONS.json').read_text())['rows']
 nominal_keys={key(np.r_[row['observation'],row['richer_previous_residual']]) for row in normal}
 train_keys={key(np.asarray(r['branch_start']['G_input'])[:58]) for r in records if r['split']=='train'}
 excluded=[];usable=[]
 for r in records:
  if r['split']=='dev' and key(np.asarray(r['branch_start']['G_input'])[:58]) in train_keys:excluded.append(r['id'])
  else:usable.append(r)
 xs=[];ys=[];splits=[];keys=[];ids=[]
 for r in usable:
  for row in r['value_rows']:
   if not row.get('feasible_success') or key(np.asarray(row['input'])[:58]) in nominal_keys:continue
   xs.append(row['input']);ys.append(row['remaining_J_F']);splits.append(r['split']);keys.append(key(row['G_input']));ids.append(r['id'])
 x=np.asarray(xs,np.float32);y=np.asarray(ys,np.float32);splits=np.asarray(splits)
 train=np.where(splits=='train')[0];dev=np.where(splits=='dev')[0];assert len(train) and len(dev),'TRAIN_DEV_REQUIRED'
 # Also remove exact/near causal duplicates from downstream dev continuation states.
 tkeys={key(x[i,:58]) for i in train};dev=np.asarray([i for i in dev if key(x[i,:58]) not in tkeys],int);assert len(dev),'NO_INDEPENDENT_DEV_STATE'
 mu=x[train].mean(0);scale=np.maximum(x[train].std(0),.02);z=(x-mu)/scale;ym=float(y[train].mean());yscale=max(float(y[train].std()),10.);yn=(y-ym)/yscale
 pairs=[]
 for k in sorted(set(keys[i] for i in train)):
  idx=[i for i in train if keys[i]==k]
  for a in idx:
   for b in idx:
    if a<b:pairs.append((a,b))
 # Ridge baseline: no hidden truth and no full-plan P feature.
 a=np.column_stack([z[train],np.ones(len(train))]);penalty=np.eye(a.shape[1])*.1;penalty[-1,-1]=0
 w=np.linalg.solve(a.T@a+penalty,a.T@yn[train]);linear=z@w[:-1]+w[-1]
 import torch
 torch.set_num_threads(1);torch.manual_seed(seed);device='cuda' if torch.cuda.is_available() else 'cpu'
 def net(out):return torch.nn.Sequential(torch.nn.Linear(120,128),torch.nn.ReLU(),torch.nn.Linear(128,128),torch.nn.ReLU(),torch.nn.Linear(128,out)).to(device)
 model=net(1);opt=torch.optim.Adam(model.parameters(),lr=.001);xt=torch.tensor(z,device=device);yt=torch.tensor(yn,device=device);tt=torch.tensor(train,device=device);dt=torch.tensor(dev,device=device)
 pa=torch.tensor([a for a,b in pairs],device=device,dtype=torch.long);pb=torch.tensor([b for a,b in pairs],device=device,dtype=torch.long)
 def metrics(pred,idx):
  costs=pred*yscale+ym;regrets=[];flips=0;groups=[]
  for k in sorted(set(keys[i] for i in idx)):
   ii=[i for i in idx if keys[i]==k]
   if len(ii)<2:continue
   best=min(ii,key=lambda i:costs[i]);true=min(ii,key=lambda i:y[i]);regrets.append(float(y[best]-y[true]));flips+=int(y[best]>y[true]+1e-6);groups.append(dict(n=len(ii),regret=float(y[best]-y[true]),spread=float(np.ptp(y[ii]))))
  return dict(RMSE=float(np.sqrt(np.mean((costs[idx]-y[idx])**2))),mean_selection_regret=float(np.mean(regrets)) if regrets else None,harmful_top1=flips,same_state_groups=len(groups),groups=groups)
 best=None;history=[]
 for epoch in range(1000):
  model.train();pred=model(xt).squeeze(1);loss=((pred[tt]-yt[tt])**2).mean()
  if len(pairs):loss=loss+10*((pred[pa]-pred[pb]-(yt[pa]-yt[pb]))**2).mean()
  opt.zero_grad();loss.backward();opt.step()
  if epoch%20==0:
   with torch.no_grad():p=model(xt).squeeze(1).cpu().numpy()
   m=metrics(p,dev);score=(m['mean_selection_regret'] if m['mean_selection_regret'] is not None else m['RMSE'],m['RMSE'])
   if best is None or score<best[0]:best=(score,{k:v.detach().cpu().clone() for k,v in model.state_dict().items()},epoch,m)
   history.append(dict(epoch=epoch,dev=m))
 model.load_state_dict(best[1]);model.eval()
 with torch.no_grad():mlp=model(xt).squeeze(1).cpu().numpy()
 lm=metrics(linear,dev);mm=metrics(mlp,dev)
 def score(m):return (m['mean_selection_regret'] if m['mean_selection_regret'] is not None else m['RMSE'],m['RMSE'])
 selected='mlp' if score(mm)<score(lm) else 'linear'
 pools={}
 for r in usable:pools.setdefault((r['split'],r['child']['snapshot_hash']),[]).append(r)
 gx=[];gy=[];gs=[];g_sources=[]
 for (split,snapshot),pool in pools.items():
  if key(np.asarray(pool[0]['branch_start']['G_input'])[:58]) in nominal_keys:continue
  ranked=sorted(pool,key=lambda r:r['remaining_J_F']);directions=[]
  B_cost=next((r['remaining_J_F'] for r in pool if r['branch_start']['source']=='B'),max(r['remaining_J_F'] for r in pool))
  ranked=[r for r in ranked if r['remaining_J_F']<B_cost-1e-6]
  if not ranked:continue
  for r in ranked:
   plan=np.asarray(r['table']).reshape(30)
   if not any(np.sqrt(np.mean((plan-q)**2))<.03 for q in directions):directions.append(plan);g_sources.append(r['id'])
   if len(directions)==3:break
  if len(directions)<2:continue
  while len(directions)<3:directions.append(directions[-1].copy())
  gx.append(ranked[0]['branch_start']['G_input']);gy.append(directions);gs.append(split)
 gnet=net(90);gopt=torch.optim.Adam(gnet.parameters(),lr=.001)
 gxx=torch.tensor((np.asarray(gx)-mu)/scale,device=device,dtype=torch.float32);gyy=torch.tensor(np.asarray(gy).reshape(-1,90),device=device,dtype=torch.float32);gt=torch.tensor([i for i,s in enumerate(gs) if s=='train'],device=device);gd=torch.tensor([i for i,s in enumerate(gs) if s=='dev'],device=device);assert len(gt),'NO_G_MULTI_DIRECTION_TARGETS'
 gbest=None
 for epoch in range(600):
  pred=torch.tanh(gnet(gxx));loss=((pred[gt]-gyy[gt])**2).mean();gopt.zero_grad();loss.backward();gopt.step()
  if epoch%20==0:
   with torch.no_grad():err=float(((torch.tanh(gnet(gxx))[gd]-gyy[gd])**2).mean()) if len(gd) else float(loss)
   if gbest is None or err<gbest[0]:gbest=(err,{k:v.detach().cpu().clone() for k,v in gnet.state_dict().items()},epoch)
 gnet.load_state_dict(gbest[1]);weights=dict(x_mean=mu,x_scale=scale,y_mean=np.array(ym),y_scale=np.array(yscale),linear_W=w[:-1],linear_b=np.array(w[-1]))
 for prefix,network in [('Q',model),('G',gnet)]:
  for i,layer in enumerate([network[0],network[2],network[4]]):weights[prefix+'_W'+str(i)]=layer.weight.detach().cpu().numpy();weights[prefix+'_b'+str(i)]=layer.bias.detach().cpu().numpy()
 np.savez_compressed(target/'weights.npz',**weights)
 def numpy_mlp(inputs,prefix):
  h=np.asarray(inputs,np.float32)
  for i in range(3):
   h=h@weights[prefix+'_W'+str(i)].T+weights[prefix+'_b'+str(i)]
   if i<2:h=np.maximum(h,0)
  return h
 with torch.no_grad():
  q_gpu=model(xt).squeeze(1).cpu().numpy();g_gpu=torch.tanh(gnet(gxx)).cpu().numpy()
 q_numpy=numpy_mlp(z,'Q').reshape(-1);g_numpy=np.tanh(numpy_mlp((np.asarray(gx,np.float32)-mu)/scale,'G'))
 parity=dict(Q_max_error_N_s=float(np.max(np.abs(q_gpu-q_numpy)))*yscale,G_max_error=float(np.max(np.abs(g_gpu-g_numpy))))
 assert parity['Q_max_error_N_s']<.005 and parity['G_max_error']<1e-5,'NUMPY_DEPLOYMENT_PARITY'
 np.savez_compressed(target/'DATASET.npz',x=x,y=y,train=train,dev=dev,source_ids=ids)
 result=dict(version=version,seed=seed,device=device,selected_Q=selected,linear_dev=lm,mlp_dev=mm,Q_best_epoch=best[2],G_best_epoch=gbest[2],G_dev_MSE=gbest[0],G_counts={s:gs.count(s) for s in set(gs)},Q_counts=dict(train=len(train),dev=len(dev)),same_state_train_pairs=len(pairs),excluded_cross_split_near_duplicates=excluded,sources=source_hashes,G_sources=g_sources,history=history,wall_s=time.time()-start,weights_sha256=sha(target/'weights.npz'),cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device=='cuda' else 0,information='B commissioned estimated inputs; direct executed outcomes; no old rolling-P or known-truth labels')
 result['peak_host_RSS_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 result['nominal_state_training_exclusion']='all 58D causal observation/history states from the saved zero-B reference are excluded from Q and G supervision; complete nominal evaluation is repeated-trajectory engineering evidence'
 save(target/'TRAINING.json',result);save(STUDY/'LATEST_WEIGHTS.json',dict(path=str(target),sha256=result['weights_sha256'],version=version,seed=seed));print(json.dumps({k:result[k] for k in ('selected_Q','linear_dev','mlp_dev','wall_s')}))
 save(target/'DEPLOYMENT_PARITY.json',dict(status='PASS',**parity))
if __name__=='__main__':main()
