from common import *
from interface import CoordinationInterface
from decompose import phase_data
from schedule import ResidualAction
def main():
 rows=read('HISTORICAL_SEGMENT_DECOMPOSITION.json')['rows'];it=CoordinationInterface();grid=np.linspace(0,1,1001);fits=[];actions={}
 for row in rows[1:]:
  folder=Path(row['result_path']).parent;z=np.load(next(folder.glob('rep_*/trace.npz')));r=dict(name=row['name'],source_trace_hash=row['trace_hash'],phases={});aa={}
  for phase in ('OUTBOUND','RETURN'):
   tape=it.tapes[phase];origin=tape.q[0];span=tape.span;s,q=phase_data(z,phase,'reference_q_rad');p=(q-origin)/span;hm=p.mean(axis=1);hd=(p[:,0]-p[:,1])/2;unique,ix=np.unique(hm,return_index=True)
   bq=np.array([tape.sample(float(x*tape.duration_s)).q_rad for x in grid]);bp=(bq-origin)/span;bm=bp.mean(axis=1);bd=(bp[:,0]-bp[:,1])/2
   target=np.interp(bm,unique,hd[ix])-bd;locations=np.linspace(0,1,101);values=np.interp(locations,grid,target);endpoint_override=[float(values[0]),float(values[-1])];values[0]=values[-1]=0
   a=ResidualAction(phase,0.,(0.,0.,0.),tuple(zip(locations[1:].tolist(),values[1:].tolist())),1.,provenance=row['name']+'_d_of_m_retimed_to_current_B')
   fitted=a.realize()(grid);pred=bp+np.stack([fitted,-fitted],axis=1);error=fitted-target
   stats=dict(normalized_path_rms=float(np.sqrt(np.mean(error**2))),normalized_path_peak=float(np.max(np.abs(error))),joint_path_rms_rad=float(np.sqrt(np.mean((span[None,:]*np.stack([error,-error],axis=1))**2))),common_mode_error=float(np.max(np.abs(pred.mean(axis=1)-bm))),progress_range=[np.min(pred,axis=0),np.max(pred,axis=0)],explicit_endpoint_zero_projection=endpoint_override,historical_m_backtracking=float(-np.sum(np.minimum(np.diff(hm),0.))),fit_pass=float(np.sqrt(np.mean(error**2)))<=.02,execution_pass=False)
   r['phases'][phase]=stats;aa[phase]=a.record()
  fits.append(r);actions[row['name']]=aa
 save('LEGACY_PATH_FITS.json',dict(rows=fits,normalization='B retained reference phase endpoints; physical arrival/settle still original task boxes',fit_rule='historical differential d(m) resampled at frozen B m(t); arbitrary 100 future knots with explicit C2 endpoint zero; no timing gain or native cost reproduction claim',execution='blocked by current B-tape realization; fit alone is not gate B/C PASS'))
 save('LEGACY_PATH_ACTIONS.json',actions);print(json.dumps(clean(fits)),flush=True)
if __name__=='__main__':main()
