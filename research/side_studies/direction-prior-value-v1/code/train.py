"""Separate CUDA process; grouped train/development model selection only."""
from pathlib import Path
import json,time,os,sys,hashlib,collections,resource
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
import numpy as np
import torch
STUDY=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/direction-prior-value-v1');L=STUDY/'output'
def save(p,x):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
def train(version=1,seed=2026100601):
 start=time.time();torch.set_num_threads(1);torch.manual_seed(seed);np.random.seed(seed);device='cuda' if torch.cuda.is_available() else 'cpu'
 target=STUDY/f'weights_v{version}_seed{seed}';target.mkdir(exist_ok=False)
 files=[p for p in L.glob('*_DATA.json') if p.name.startswith(('parent_train_','parent_dev_'))];records=[json.loads(p.read_text()) for p in files];assert all(r['split'] in ('train','dev') for r in records),'TRAIN_FILENAME_SPLIT_MISMATCH';usable=[r for r in records if r.get('metric',{}).get('valid')]
 sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if json.loads(p.read_text()).get('split') in ('train','dev')};assert not any(r['split']=='test' for r in usable)
 V={};G={};groups=collections.defaultdict(list)
 for r in usable:
  groups[(r['split'],hashlib.sha256(np.asarray(r['branch_start']['G_input'],np.float32).tobytes()).hexdigest())].append(r)
  for i,row in enumerate(r['value_rows']):
   if 'input' not in row or not row['feasible_success']:continue
   inputs=np.asarray(row['input'],np.float32).copy();pending=inputs[58:88].reshape(2,5,3)
   for j,phase in enumerate(('OUTBOUND','RETURN')):pending[j,:row['count'][phase]]=0.
   V.setdefault(r['split'],[]).append((inputs,row['deltaV_label'],row['V_base'],row['remaining_J_F'],r['child']['label'] if i==0 else None))
 parent_carry=[]
 if version>=2:
  parent_path=L/'020_parent_train_1_RESULT.json';decision_path=L/'020_parent_train_1_DECISIONS.json';parent=json.loads(parent_path.read_text())
  if parent.get('metric',{}).get('valid') and parent['metric']['status']=='COMPLETE':
   decisions=json.loads(decision_path.read_text())['rows'];table=parent['inputs']['table']
   # Already-counted parent executes this table with native certification,
   # not SearchInterface replanning. Its actual suffix is compatible pi_cont.
   # Reuse that successful trajectory for G only; no inferred V_base labels.
   for phase,index in (('OUTBOUND',0),('OUTBOUND',2),('OUTBOUND',4),('RETURN',1)):
    row=next(r for r in decisions if r['phase']==phase and r['native_index']==index);label=f'parent_train_1_{phase}_{index}';anchor=next(r for r in records if r['group']=='parent_train_1' and r['child']['label']==label)
    assert np.array_equal(row['observation'],anchor['branch_start']['context']['observation']) and np.array_equal(row['richer_previous_residual'],anchor['branch_start']['context']['richer_previous_residual']),'PARENT_CARRY_CAUSAL_STATE_MISMATCH'
    r=dict(id=label+'_actual_parent_suffix',split='train',group='parent_train_1',branch_start=anchor['branch_start'],table=table,remaining_J_F=parent['metric']['J_F']-row['measured_prefix_J_F'],source_role='G-only actual successful committed-parent suffix; no per-state reoptimization')
    groups[('train',hashlib.sha256(np.asarray(r['branch_start']['G_input'],np.float32).tobytes()).hexdigest())].append(r);parent_carry.append(dict(id=r['id'],remaining_J_F=r['remaining_J_F'],source_role=r['source_role']))
   sources.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (parent_path,decision_path)})
 g_source_targets=collections.Counter()
 for (split,group),rows in groups.items():
  best=[];seen=set()
  for r in sorted(rows,key=lambda r:r['remaining_J_F']):
   pending=np.asarray(r['table'],np.float32).copy()
   for j,phase in enumerate(('OUTBOUND','RETURN')):pending[j,:r['branch_start']['counts'][phase]]=0.
   key=pending.tobytes()
   if key in seen:continue
   seen.add(key);best.append((r,pending))
   if len(best)==3:break
  for rank,(r,pending) in enumerate(best):
   G.setdefault(split,[]).append((r['branch_start']['G_input'],pending.ravel(),group,rank));g_source_targets[r.get('source_role','independently measured physical branch')]+=1
 # Entire parents keep their split. Identical common initial/B/K3 trajectories
 # can still recur across different parents; exclude exact representation
 # duplicates from development selection and merge same-state proposal heads.
 dedup={}
 for kind,collection in (('V',V),('G',G)):
  trained={np.asarray(row[0],np.float32).tobytes() for row in collection['train']};before=len(collection['dev']);collection['dev']=[row for row in collection['dev'] if np.asarray(row[0],np.float32).tobytes() not in trained];dedup[kind]=dict(dev_before=before,dev_after=len(collection['dev']),exact_train_feature_duplicates_excluded=before-len(collection['dev']))
 assert len(V.get('train',[]))>=10 and len(V.get('dev',[]))>=5,'INSUFFICIENT_GROUPED_VALID_LABELS'
 weights={};metrics={};criterion={}
 def arrays(data):return np.asarray([r[0] for r in data],np.float32),np.asarray([r[1] for r in data],np.float32)
 def stats(x):return x.mean(0),np.maximum(x.std(0),.05)
 def export(kind,network,mean,scale):
  weights[kind+'_mean']=mean;weights[kind+'_scale']=scale
  for i,layer in enumerate([network[0],network[2],network[4]]):weights[kind+f'_W{i}']=layer.weight.detach().cpu().numpy();weights[kind+f'_b{i}']=layer.bias.detach().cpu().numpy()
 x,y=arrays(V['train']);xd,yd=arrays(V['dev']);mean,scale=stats(x);ym=float(y.mean());ys=max(float(y.std()),1.)
 xt=torch.tensor((x-mean)/scale,device=device);yt=torch.tensor((y-ym)/ys,device=device).unsqueeze(-1);dt=torch.tensor((xd-mean)/scale,device=device)
 net=torch.nn.Sequential(torch.nn.Linear(x.shape[1],128),torch.nn.ReLU(),torch.nn.Linear(128,128),torch.nn.ReLU(),torch.nn.Linear(128,1)).to(device);opt=torch.optim.Adam(net.parameters(),lr=.001,weight_decay=.0001)
 best_state=None;best_loss=float('inf');history=[]
 def rankloss(pred):
  costs=np.asarray([r[2] for r in V['dev']])+pred;truth=np.asarray([r[3] for r in V['dev']]);regrets=[];correct=0;total=0
  for group in sorted({r[4] for r in V['dev'] if r[4] is not None}):
   idx=np.asarray([i for i,r in enumerate(V['dev']) if r[4]==group]);choice=idx[np.argmin(costs[idx])];regrets.append(float(truth[choice]-truth[idx].min()));correct+=int(choice==idx[np.argmin(truth[idx])]);total+=1
  return dict(selection_regret_Ns=float(np.mean(regrets)) if regrets else None,top1_correct=correct,groups=total,deltaV_RMSE=float(np.sqrt(np.mean((pred-yd)**2))))
 for epoch in range(401):
  net.train();opt.zero_grad();loss=torch.nn.functional.mse_loss(net(xt),yt);loss.backward();opt.step()
  if epoch%20==0:
   net.eval()
   with torch.no_grad():pred=net(dt).squeeze(-1).cpu().numpy()*ys+ym
   met=rankloss(pred);score=met['selection_regret_Ns']+met['deltaV_RMSE']*.01
   history.append(dict(epoch=epoch,train_loss=float(loss.item()),**met))
   if score<best_loss:best_loss=score;best_state={k:v.detach().clone() for k,v in net.state_dict().items()}
 net.load_state_dict(best_state);net.eval()
 with torch.no_grad():mlp_pred=net(dt).squeeze(-1).cpu().numpy()*ys+ym
 export('V',net,mean,scale);weights['V_target_mean']=np.asarray(ym);weights['V_target_scale']=np.asarray(ys)
 design=np.column_stack([np.ones(len(x)),(x-mean)/scale]);reg=np.eye(design.shape[1]);reg[0,0]=0.;coef=np.linalg.solve(design.T@design+10.*reg,design.T@((y-ym)/ys));linear_pred=np.column_stack([np.ones(len(xd)),(xd-mean)/scale])@coef*ys+ym
 metrics['V_MLP']=rankloss(mlp_pred);metrics['V_LINEAR']=rankloss(linear_pred)
 def selectscore(m):return m['selection_regret_Ns']+.01*m['deltaV_RMSE']
 chosen=int(selectscore(metrics['V_LINEAR'])<selectscore(metrics['V_MLP']));weights['V_type']=np.asarray(chosen);weights['V_linear']=coef.astype(np.float32);metrics['V_selected']='LINEAR' if chosen else 'MLP'
 gx,gy=arrays(G['train']);gdx,gdy=arrays(G['dev']);gm,gs=stats(gx);gxt=torch.tensor((gx-gm)/gs,device=device);gyt=torch.tensor(gy,device=device)
 gnet=torch.nn.Sequential(torch.nn.Linear(gx.shape[1],128),torch.nn.ReLU(),torch.nn.Linear(128,128),torch.nn.ReLU(),torch.nn.Linear(128,90)).to(device);gopt=torch.optim.Adam(gnet.parameters(),lr=.001,weight_decay=.0001)
 # Fixed rank assignment maintains three distinct good directions, never averages opposites.
 ranks=torch.tensor([r[3] for r in G['train']],device=device);indices=torch.arange(len(ranks),device=device)
 for epoch in range(401):
  gopt.zero_grad();pred=torch.tanh(gnet(gxt)).reshape(-1,3,30);gloss=torch.nn.functional.mse_loss(pred[indices,ranks],gyt);gloss.backward();gopt.step()
 export('G',gnet,gm,gs)
 with torch.no_grad():gpred=torch.tanh(gnet(torch.tensor((gdx-gm)/gs,device=device))).reshape(-1,3,30).cpu().numpy()
 metrics['G_dev_nearest_head_plan_RMS']=float(np.sqrt(np.mean(np.min(np.mean((gpred-gdy[:,None,:])**2,axis=-1),axis=1))))
 weights_path=target/'networks.npz';np.savez_compressed(weights_path,**weights)
 # Verify saved NumPy inference against the trained device before release.
 sys.path.insert(0,str(STUDY/'code'));from inference import Networks
 cpu=Networks(weights_path);pred=np.array([cpu.value(row) for row in xd]);selected_pred=linear_pred if chosen else mlp_pred
 metrics['V_numpy_device_max_difference_Ns']=float(np.max(np.abs(pred-selected_pred)));metrics['G_numpy_device_max_difference']=float(np.max(np.abs(cpu.proposals(gdx[0])-gpred[0])))
 assert metrics['V_numpy_device_max_difference_Ns']<.01 and metrics['G_numpy_device_max_difference']<1e-4
 summary=dict(version=version,seed=seed,device=device,torch_version=torch.__version__,network_hidden=[128,128],G_heads=3,V_selected=metrics['V_selected'],V_label='actual complete remaining J_F minus model remainder at the same causal native state and committed suffix',continuation='native-certified-committed-K3-suffix-v1',feature_semantics='103D; executed past table rows zeroed; causal previous residual kept; committed future plan and counts explicit; earlier raw feature rows remapped by recorded count without relabelling costs',data_sources=sources,group_splits={s:sorted({r['group'] for r in usable if r['split']==s}) for s in ('train','dev')},representation_deduplication=dedup,G_target_semantics='three distinct best measured pending plans per identical float32 causal input; common states merged within a split, unused past target rows masked; no averaging across opposite plans',V_counts={s:len(v) for s,v in V.items()},G_counts={s:len(v) for s,v in G.items()},metrics=metrics,history=history,weights=str(weights_path),weights_sha256=hashlib.sha256(weights_path.read_bytes()).hexdigest(),wall_s=time.time()-start,test_used=False)
 summary['peak_host_rss_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 summary['actual_parent_suffix_G_supervision']=parent_carry;summary['G_target_source_counts']=dict(g_source_targets)
 summary['training_script']=str(Path(__file__).resolve());summary['training_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 summary['inference_source_sha256']=hashlib.sha256((STUDY/'code/inference.py').read_bytes()).hexdigest()
 summary['CUDA_peak_allocated_bytes']=torch.cuda.max_memory_allocated() if device=='cuda' else None
 summary['CUDA_peak_reserved_bytes']=torch.cuda.max_memory_reserved() if device=='cuda' else None
 save(target/'TRAINING.json',summary);save(STUDY/'LATEST_WEIGHTS.json',summary);print(json.dumps(dict(weights=str(weights_path),metrics=metrics,wall_s=summary['wall_s'])),flush=True)
if __name__=='__main__':train(int(sys.argv[1]) if len(sys.argv)>1 else 1,int(sys.argv[2]) if len(sys.argv)>2 else 2026100601)
