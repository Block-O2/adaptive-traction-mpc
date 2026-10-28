"""Same executable legacy square; rotate search directions only."""
import copy
import numpy as np
from acl2_shared import put,utc
def sequence(study,C):
 for tag,fam in [('B','B'),('H150','legacy2')]:yield dict(tag=tag,action=dict(family=fam,legacy=[0,0]))
 base=copy.deepcopy(study.last_row);rows={a:[] for a in ['NATIVE','ROTATED']};study.arm_rows=rows
 design=np.array([[.5,0],[-.5,0],[0,.5],[0,-.5]])
 for n in range(C['per_arm']):
  for arm in rows:
   own=rows[arm];best=min([base]+[r for r in own if r.get('qualified')],key=lambda r:r['JF']);center=np.asarray(best['action'].get('legacy',[0,0]));seen=np.array([[0,0]]+[r['action']['legacy'] for r in own])
   if n<4:x=design[n]
   else:
    dirs=np.eye(2) if arm=='NATIVE' else np.array([[1,1],[1,-1]])/np.sqrt(2)
    pool=[center+sign*step*d for step in [.5,.25,.125,.0625,.03125] for d in dirs for sign in [1,-1]]
    x=next(z for z in pool if np.all(abs(z)<=1+1e-12) and np.min(np.linalg.norm(seen-z,axis=1))>1e-8)
   yield dict(tag=arm+'_%03d'%(n+1),action=dict(family='legacy2',legacy=x.tolist(),coordinates=arm,latent=((x[0]+x[1])/2,(x[0]-x[1])/2) if arm=='ROTATED' else x.tolist()),category='optimization')
   row=copy.deepcopy(study.last_row);row['arm']=arm;own.append(row)
 put('jobs/'+study.condition['name']+'/SELECTION.json',dict(utc=utc(),rows=rows,per_arm=C['per_arm'],best={a:min([base]+[r for r in rows[a] if r['qualified']],key=lambda r:r['JF']) for a in rows},physical_domain='same x square [-1,1]^2',coordinate_domain='u,v diamond |u+v|<=1, |u-v|<=1',step_Euclidean_norm_matched=True,no_new_reference_permissions=True))
