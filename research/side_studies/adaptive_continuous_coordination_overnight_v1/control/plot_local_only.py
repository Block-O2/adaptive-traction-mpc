from pathlib import Path
import os,sys,json
os.environ['MPLBACKEND']='Agg'
import matplotlib.pyplot as plt
import numpy as np
P=Path(__file__).resolve().parents[1];sys.path.insert(0,str(P/'prototype'))
from continuous import Piece,LocalQuintic,LocalTimeWarp
e=json.loads((P/'prototype/EXAMPLE_CURVES.json').read_text())
o=Piece(np.array(e['original']['coefficients']),e['original']['duration_s']);T=o.T;local=LocalQuintic.from_piece(o,[.2*T,.4*T,.6*T,.8*T]);changed=local.update(2,dq=np.radians([.3,-.2]),dv=np.radians([.2,.1]),da=np.radians([.1,-.1]));tt=np.linspace(0,T,4001);delta=changed.evaluate(tt)-local.evaluate(tt);warp=LocalTimeWarp(local,.2*T,.8*T,.02*T);sp=o.bspline()
for fraction in [.15,.3,.45,.6,.75,.9]:sp=sp.insert_knot(T*fraction)
mut=sp.c.copy();mut[6]+=np.radians([.2,-.2]);alt=type(sp)(sp.t,mut,sp.k);spdelta=alt(tt)-sp(tt)
fig,ax=plt.subplots(3,1,figsize=(11,9),sharex=True)
ax[0].plot(tt,np.rad2deg(delta));ax[0].set_ylabel('Local path change (deg)');ax[0].legend(['hip','knee']);ax[1].plot(tt,np.rad2deg(warp.evaluate(tt,1)-local.evaluate(tt,1)));ax[1].set_ylabel('Time-warp dq change (deg/s)');ax[2].plot(tt,np.rad2deg(spdelta));ax[2].set_ylabel('B-spline control effect (deg)')
for a in ax:a.grid(alpha=.2)
ax[-1].set_xlabel('Local schedule time (s)');fig.suptitle('Nonzero local mathematical authority, no new physical claim');fig.tight_layout();fig.savefig(P/'figures/local_control_effect.png',dpi=160);plt.close(fig)
