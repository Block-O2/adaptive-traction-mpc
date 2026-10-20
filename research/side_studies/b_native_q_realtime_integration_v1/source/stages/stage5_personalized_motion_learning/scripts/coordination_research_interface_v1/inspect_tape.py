from common import *
z=np.load(L/'B_TAPE.npz')
for phase in ('OUTBOUND','HOLD','RETURN'):
 mask=z['phase']==phase;t=z['t'][mask];q=z['q'][mask];v=z['v'][mask];a=z['a'][mask]
 dq=np.diff(q,axis=0)/np.diff(t)[:,None];err=dq-(v[:-1]+v[1:])/2
 ids=np.argsort(np.max(np.abs(err),axis=1))[-5:]
 print(phase,'q vel err',np.max(np.abs(err)), 'ddqpeak',np.max(np.abs(a)),flush=True)
 for i in ids:print(dict(t=t[i:i+2].tolist(),q=q[i:i+2].tolist(),v=v[i:i+2].tolist(),a=a[i:i+2].tolist(),err=err[i].tolist()),flush=True)
