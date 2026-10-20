from common import *
z=np.load(O/'HISTORY_RL.npz'); live=~(z['terminated']|z['truncated']); rows=[]
for name in dict.fromkeys(z['episode'].tolist()):
 ids=np.flatnonzero((z['episode']==name)&live); raw=z['next_observations'][ids,49:51]-z['actions'][ids]; safe=z['next_observations'][ids,51:53]-z['executed_actions'][ids]
 if np.any(raw) or np.any(safe):
  j=int(np.argmax(np.max(np.abs(safe),1))); i=int(ids[j]);rows.append(dict(episode=name,n=len(ids),raw_max=float(np.abs(raw).max()),safe_max=float(np.abs(safe).max()),index=i,obs_next=z['next_observations'][i,47:55],action=z['actions'][i],executed=z['executed_actions'][i],executed_dtype=str(z['executed_actions'].dtype),obs_dtype=str(z['next_observations'].dtype)))
save('ACTION_ECHO_DIAGNOSIS.json',dict(rows=rows,scales=SCALES));print(json.dumps(clean(rows)))
