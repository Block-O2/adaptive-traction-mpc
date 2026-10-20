from research_common import *
import collections, itertools, resource

STATE=np.r_[0:58,88:120]
def key58(x):return np.round(np.asarray(x,np.float32)[:58],4).tobytes()
def predict_frozen(w,x,kind):
 z=(np.asarray(x,np.float32)-w['x_mean'])/w['x_scale']
 if kind=='linear':p=z@w['linear_W']+w['linear_b']
 else:
  h=z
  for i in range(3):
   h=h@w[f'Q_W{i}'].T+w[f'Q_b{i}']
   if i<2:h=np.maximum(h,0)
  p=h[:,0]
 return p*float(w['y_scale'])+float(w['y_mean'])
def labels(r):
 path=MATRIX/'source/results'/r['id']/'trace.npz'
 z,ix,q=unique_trace(path);at=r['child']['physical_time_at_fork'];ix=ix[z['time_s'][ix]>=at-1e-8]
 t=z['time_s'][ix];v=z['evaluation_only_human_state_rad_rad_s'][ix,2:];a=np.gradient(v,t,axis=0,edge_order=2);j=np.gradient(a,t,axis=0,edge_order=2)
 err=np.rad2deg(z['evaluation_only_human_state_rad_rad_s'][ix,:2]-z['reference_q_rad'][ix]);f=np.linalg.norm(z['physical_cuff_force_world_n'][ix],axis=1);m=np.linalg.norm(z['physical_cuff_moment_world_nm'][ix],axis=1)
 return {'trace':str(path),'trace_sha256':sha(path),'remaining_start_s':at,'sampled_velocity_deg_s':stats(np.rad2deg(v)),'sampled_acceleration_deg_s2':stats(np.rad2deg(a)),'sampled_jerk_deg_s3':stats(np.rad2deg(j)),'sampled_force_peak_N':float(f.max()),'remaining_moment_integral_native_Nm_s':r['remaining_M'],'sampled_moment_peak_Nm':float(m.max()),'tracking_RMS_deg':np.sqrt(np.mean(err**2,axis=0)).tolist(),'measured_sleeve_clearance_min_m':float(z['dev_d_measured_sleeve_gap_m'][ix].min()),'session_shank_clearance_min_m':float(z['session_shank_clearance_m'][ix].min()),'duration_remaining_s':float(t[-1]-at),'actual_angle_excursion_deg':np.rad2deg(np.ptp(z['evaluation_only_human_state_rad_rad_s'][ix,:2],axis=0)).tolist(),'complete_valid':True,'native_physical_audit':r['metric']['physical_audit'],'signal_limit':'5ms trace differentiation; not native-resolution jerk qualification'}
def evaluate(y,p,groups,idx,rows):
 records=[];total=correct=0
 for g in sorted(set(groups[idx])):
  ii=idx[groups[idx]==g]
  if len(ii)<2:continue
  order=np.argsort(p[ii],kind='stable');selected=int(ii[order[0]]);best=float(np.min(y[ii]));pairs=[]
  for a,b in itertools.combinations(ii,2):
   if abs(y[a]-y[b])<=1e-6:continue
   ok=int(np.sign(p[a]-p[b])==np.sign(y[a]-y[b]));correct+=ok;total+=1;pairs.append({'a':rows[a]['id'],'b':rows[b]['id'],'true_delta_N_s':float(y[a]-y[b]),'predicted_delta_N_s':float(p[a]-p[b]),'correct':bool(ok)})
  records.append({'snapshot':g,'candidate_count':len(ii),'actual_spread_N_s':float(np.ptp(y[ii])),'selected_id':rows[selected]['id'],'best_ids':[rows[k]['id'] for k in ii if y[k]<=best+1e-6],'selected_remaining_J_F_N_s':float(y[selected]),'oracle_remaining_J_F_N_s':best,'regret_N_s':float(y[selected]-best),'top1_correct':bool(y[selected]<=best+1e-6),'pairs':pairs,'selected_motion':rows[selected]['labels'],'candidate_rows':[{'id':rows[k]['id'],'source':rows[k]['candidate_source'],'true_cost_N_s':float(y[k]),'pred_cost_N_s':float(p[k]),'labels':rows[k]['labels']} for k in ii]})
 return {'RMSE_N_s':float(np.sqrt(np.mean((p[idx]-y[idx])**2))),'MAE_N_s':float(np.mean(abs(p[idx]-y[idx]))),'same_state_groups':len(records),'pairwise_accuracy':correct/total if total else None,'non_tied_pairs':total,'mean_selection_regret_N_s':float(np.mean([r['regret_N_s'] for r in records])) if records else None,'top1_accuracy':float(np.mean([r['top1_correct'] for r in records])) if records else None,'groups':records}
def main():
 budget();protocol=load(OUT/'PREREGISTERED_PROTOCOL.json');start=time.time()
 records=[];excluded=[];failed=[];all_source=[]
 for path in sorted((MATRIX/'output').glob('*_DATA.json')):
  r=load(path);all_source.append({'path':str(path),'sha256':sha(path),'group':r['group'],'valid':r['metric']['valid']})
  if not r['metric']['valid'] or r['metric']['status']!='COMPLETE':failed.append({'id':r['id'],'metric':r['metric'],'status':r['status']});continue
  split=next((s for s,gs in protocol['split'].items() if isinstance(gs,list) and r['group'] in gs),None)
  if split is None:excluded.append({'id':r['id'],'reason':'outside fixed source split'});continue
  x=np.array(r['branch_start']['input'],np.float32);y=r['remaining_J_F'];assert x.shape==(120,) and np.all(np.isfinite(x)) and y>=0
  assert r['continuation']=='native-certified-committed-K3-suffix-v1'
  assert abs(y-r['value_rows'][0]['remaining_J_F'])<1e-6
  table=np.array(r['table']).reshape(2,5,3).copy()
  for d,ph in enumerate(['OUTBOUND','RETURN']):table[d,:min(r['branch_start']['counts'][ph],5)]=0
  assert np.max(abs(table.ravel()-x[58:88]))<1e-6
  records.append({'id':r['id'],'parent':r['group'],'split':split,'snapshot':r['child']['snapshot_hash'],'x':x,'y':y,'candidate_source':r['branch_start']['source'],'source_file':str(path),'source_sha256':sha(path),'raw':r})
 prior=set();usable=[]
 for split in ['train','validation','test']:
  a=[r for r in records if r['split']==split];bad={r['snapshot'] for r in a if key58(r['x']) in prior}
  for r in a:
   if r['snapshot'] in bad:excluded.append({'id':r['id'],'reason':'cross-split causal58 near-duplicate snapshot excluded wholesale'})
   else:usable.append(r)
  prior.update(key58(r['x']) for r in a if r['snapshot'] not in bad)
 rows=usable
 for r in rows:r['labels']=labels(r['raw']);del r['raw']
 x=np.array([r['x'] for r in rows]);y=np.array([r['y'] for r in rows]);groups=np.array([r['snapshot'] for r in rows]);splits=np.array([r['split'] for r in rows])
 indices={s:np.flatnonzero(splits==s) for s in ['train','validation','test']}
 for s,idx in indices.items():assert len(idx)>0
 for g in set(groups):
  ii=np.flatnonzero(groups==g);assert len(set(splits[ii]))==1 and np.max(np.ptp(x[ii][:,STATE],axis=0))<1e-6,'STATE_GROUP_MISMATCH'
 assert not any(set(key58(x[i]) for i in indices[a])&set(key58(x[i]) for i in indices[b]) for a,b in itertools.combinations(indices,2))
 np.savez_compressed(OUT/'NEURAL_DATASET.npz',x=x,y=y,split=splits,snapshot=groups,source_ids=np.array([r['id'] for r in rows]))
 save('BRANCH_LABELS.json',{'rows':[{k:v for k,v in r.items() if k!='x'} for r in rows],'failed_rows':failed,'excluded_rows':excluded,'all_sources':all_source})
 save('DATASET_AUDIT.json',{'status':'EXPLORATORY_SUFFICIENT_FOR_BOUNDED_PROTOTYPE','rows':len(rows),'split_counts':{s:len(idx) for s,idx in indices.items()},'snapshot_counts':{s:len(set(groups[idx])) for s,idx in indices.items()},'independent_parent_sources':{s:sorted(set(rows[i]['parent'] for i in idx)) for s,idx in indices.items()},'cross_split_causal58_overlap':0,'same_full_state_branch_grouping':True,'labels':'actual native full remaining repetition force, shared complete address-space fork snapshots; no q/dq reconstruction','restoration_gate':load(MATRIX/'BRANCH_GATE.json'),'original_dataset_sha256':sha(FROZEN/'DATASET.npz'),'new_dataset_sha256':sha(OUT/'NEURAL_DATASET.npz'),'counterfactual_rollouts':0,'failed_count':len(failed),'excluded':excluded,'effective_scale_warning':'few parent trajectories and state groups; historical diagnostic test is exposed; frozen Q has seen train/development sources; no new-Human inference','capacity_choice':'16x16 and32x32 challenger instead of historical128x128; no broad search; absolute labels only at actual fork start; downstream rows not inflated into states','motion_label_limit':'sampled 5ms trace labels; dense-native host burden separately; auxiliary heads not trained'})
 import torch
 torch.set_num_threads(1);torch.manual_seed(protocol['seed']);train=indices['train'];val=indices['validation'];test=indices['test']
 mu=x[train].mean(0);scale=np.maximum(x[train].std(0),.02);ym=float(y[train].mean());ys=max(float(y[train].std()),10.)
 z=(x-mu)/scale;yn=(y-ym)/ys
 xt=torch.tensor(z,dtype=torch.float32);yt=torch.tensor(yn,dtype=torch.float32)
 pairs=[(a,b) for g in sorted(set(groups[train])) for a,b in itertools.combinations(train[groups[train]==g],2)]
 pa=torch.tensor([a for a,b in pairs]);pb=torch.tensor([b for a,b in pairs])
 (OUT/'models').mkdir(exist_ok=True);candidates=[]
 for hidden in protocol['architectures']:
  budget();torch.manual_seed(protocol['seed']);net=torch.nn.Sequential(torch.nn.Linear(120,hidden[0]),torch.nn.ReLU(),torch.nn.Linear(hidden[0],hidden[1]),torch.nn.ReLU(),torch.nn.Linear(hidden[1],1));opt=torch.optim.Adam(net.parameters(),lr=protocol['learning_rate'],weight_decay=protocol['weight_decay']);best=None;history=[]
  for epoch in range(protocol['epochs']):
   p=net(xt).squeeze(1);loss=((p[train]-yt[train])**2).mean()+10*((p[pa]-p[pb]-(yt[pa]-yt[pb]))**2).mean();opt.zero_grad();loss.backward();opt.step()
   if epoch%10==0:
    with torch.no_grad():pred=net(xt).squeeze(1).numpy()*ys+ym
    metrics=evaluate(y,pred,groups,val,rows);score=(metrics['mean_selection_regret_N_s'],metrics['RMSE_N_s']);history.append({'epoch':epoch,'loss':float(loss.detach()),'validation_regret_N_s':score[0],'validation_RMSE_N_s':score[1]})
    if best is None or score<best[0]:best=(score,{k:v.detach().clone() for k,v in net.state_dict().items()},epoch)
  net.load_state_dict(best[1]);net.eval();path=OUT/'models'/('Q_'+str(hidden[0])+'.npz');assert not path.exists()
  weights={'x_mean':mu,'x_scale':scale,'y_mean':np.array(ym),'y_scale':np.array(ys)}
  for n,l in enumerate([net[0],net[2],net[4]]):weights['Q_W'+str(n)]=l.weight.detach().numpy();weights['Q_b'+str(n)]=l.bias.detach().numpy()
  np.savez_compressed(path,**weights)
  with torch.no_grad():pt=net(xt).squeeze(1).numpy()*ys+ym
  pn=predict_frozen(weights,x,'mlp');parity=float(np.max(abs(pt-pn)));assert parity<.005
  candidate={'hidden':hidden,'parameters':sum(p.numel() for p in net.parameters()),'path':str(path),'sha256':sha(path),'selected_epoch':best[2],'validation_score':best[0],'history':history,'torch_numpy_max_error_N_s':parity}
  candidates.append(candidate);print('TRAINED',hidden,'VAL',best[0],flush=True)
 chosen=min(candidates,key=lambda c:tuple(c['validation_score']))
 save('MODEL_SELECTION_FROZEN.json',{'chosen':chosen,'selection_unix':time.time(),'selection_rule':protocol['selection'],'test_evaluated_for_selection':False,'all_candidates':candidates})
 with np.load(chosen['path']) as f:nw={k:f[k].copy() for k in f.files}
 with np.load(FROZEN/'weights.npz') as f:fw={k:f[k].copy() for k in f.files}
 ps={'A_frozen_linear':predict_frozen(fw,x,'linear'),'B_historical_MLP120':predict_frozen(fw,x,'mlp'),'C_neural_challenger':predict_frozen(nw,x,'mlp')}
 results={name:{s:evaluate(y,p,groups,idx,rows) for s,idx in indices.items()} for name,p in ps.items()}
 sensitivity=[]
 for ratio in protocol['B_relative_sensitivity']:
  for name,p in ps.items():
   for g in sorted(set(groups[test])):
    ii=test[groups[test]==g];base=next((i for i in ii if np.max(abs(x[i,58:88]))<1e-8),None)
    if base is None:sensitivity.append({'model':name,'snapshot':g,'ratio':ratio,'status':'NOT_EVALUABLE_NO_B_BRANCH'});continue
    eligible=[]
    for i in ii:
     ok=True
     for sig in ['sampled_velocity_deg_s','sampled_acceleration_deg_s2','sampled_jerk_deg_s3']:
      for met in ['max_abs','p95_abs','p99_abs']:
       ok &= bool(np.all(np.asarray(rows[i]['labels'][sig][met])<=ratio*np.asarray(rows[base]['labels'][sig][met])+1e-9))
     if ok:eligible.append(i)
    selected=min(eligible,key=lambda i:p[i]) if eligible else None
    sensitivity.append({'model':name,'snapshot':g,'ratio':ratio,'status':'DESCRIPTIVE_B_RELATIVE_FILTER','B_id':rows[base]['id'],'eligible_ids':[rows[i]['id'] for i in eligible],'selected_id':rows[selected]['id'] if selected is not None else None,'remaining_J_F_N_s':y[selected] if selected is not None else None,'safety':'all included branches native-valid COMPLETE','qualification':'outcome-oracle filter sensitivity only; not deployable gate; ratios are not clinical limits'})
 # Structural interaction probes keep candidate tables and masks identical across states.
 probes=[];states=x[[train[0],val[0],test[0]]].copy();states[:,58:120]=0
 for name,w,kind in [('A_frozen_linear',fw,'linear'),('B_historical_MLP120',fw,'mlp'),('C_neural_challenger',nw,'mlp')]:
  a=states.copy();b=states.copy();a[:,58:88]=.2;b[:,58:88]=-.2;delta=predict_frozen(w,a,kind)-predict_frozen(w,b,kind)
  probes.append({'model':name,'fixed_plan_pair_score_differences_N_s':delta,'mixed_difference_range_N_s':np.ptp(delta),'role':'structural joint-model capability only; synthetic plan feature probes, no rollout or efficacy claim'})
 lat=[]
 for name,w,kind in [('A_frozen_linear',fw,'linear'),('B_historical_MLP120',fw,'mlp'),('C_neural_challenger',nw,'mlp')]:
  batch=x[test[:min(9,len(test))]]
  for _ in range(20):predict_frozen(w,batch,kind)
  ts=[]
  for _ in range(300):
   at=time.perf_counter_ns();predict_frozen(w,batch,kind);ts.append((time.perf_counter_ns()-at)/1e6)
  lat.append({'model':name,'batch_size':len(batch),'CPU_numpy_ms':stats(np.array(ts)),'p50_ms':np.median(ts),'parameter_and_normalization_bytes':sum(v.nbytes for v in w.values() if isinstance(v,np.ndarray) and not str(v.dtype).startswith('<U')),'scope':'offline single-thread microbenchmark; excludes candidate construction, native admission and host contention; no runtime qualification'})
 save('NEURAL_Q_EVALUATION.json',{'status':'EXPLORATORY','models':results,'test_source_exposed':True,'same_candidates_and_legal_observed_branches':True,'motion_filter_sensitivity':sensitivity,'interaction_probes':probes,'inference':lat,'test_not_used_for_model_selection':True,'decisional_advantage_gate':'UNRESOLVED independent evidence; exposed-test regret comparison reported directly','ranking_inversions':'No target inversion count; correct ranking judged against actual candidate costs; fixed order may be optimal','failure_modes':'few state sources, committed-suffix candidate supervision differs from repeated replanning policy; sampled auxiliary labels cannot qualify sub-ms safety'})
 save('TRAINING_MANIFEST.json',{'status':'EXPLORATORY_TRAINED','protocol_sha256':sha(OUT/'PREREGISTERED_PROTOCOL.json'),'dataset':str(OUT/'NEURAL_DATASET.npz'),'dataset_sha256':sha(OUT/'NEURAL_DATASET.npz'),'splits':{s:[rows[i]['id'] for i in idx] for s,idx in indices.items()},'normalization_train_only':True,'config':protocol,'chosen_model':chosen,'candidates':[{k:v for k,v in c.items() if k!='history'} for c in candidates],'same_state_train_pair_count':len(pairs),'wall_s':time.time()-start,'peak_process_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'torch_version':torch.__version__,'numpy_version':np.__version__,'device':'CPU single thread','new_physical_rollouts':0,'host_runs':0,'G_P_training':0})
 save('MODEL_AND_FEATURE_CONTRACT.json',{'status':'FROZEN_EXPLORATORY_CHALLENGER_NOT_HOST_QUALIFIED','model':chosen['path'],'sha256':chosen['sha256'],'architecture':[120]+chosen['hidden']+[1],'feature_dtype':'float32','feature_layout':protocol['inputs'],'feature_source_implementation':str(MATRIX/'code/native_core.py'),'feature_source_sha256':sha(MATRIX/'code/native_core.py'),'mask_rule':'zero issued OUTBOUND/RETURN slots 0:min(count,5) before flattening candidate and carry; original K3 normalized semantics, graph_action scale .2','normalization':'(x-training mean)/max(training std,.02); scalar output * max(training y std,10) + training y mean','score_contract':'finite batch Nx120 -> remaining J_F N s. Ranking ascending; legal mask/admission/safety/carry remain native caller responsibilities. This scorer has no actuation or state mutation.','scorer':'offline_score.py','truth_firewall':'only original deployable observation/history/plan/carry/count inputs; dense native truth solely audit labels','continuation':'native-certified-committed-K3-suffix-v1 labels; not certified repeated online replanning policy value','feature_availability':'native120D already available in prior TASK scoring path; no new deployment feature','frozen_original_Q_sha256':sha(FROZEN/'weights.npz'),'host_activation':False})
 print('TEST_METRICS',json.dumps({n:{k:v for k,v in a['test'].items() if k!='groups'} for n,a in results.items()}),flush=True)
if __name__=='__main__':main()
