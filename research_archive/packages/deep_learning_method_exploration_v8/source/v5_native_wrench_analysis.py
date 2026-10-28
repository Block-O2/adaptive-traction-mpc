"""Analyze actual saved 4 kHz wrench without replacing original 200 Hz JF/JM."""
from pathlib import Path
import os,sys,json,gzip
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
from v5_metrics import stats,wrench,put,P
def analyze(ident):
 p=P/'runtime/source/results'/ident
 with gzip.open(p/'runtime_artifacts.json.gz','rt') as f:raw=json.load(f)
 n=raw['wall_physics']['native_states_evaluation_only']
 if not n or 'cuff_wrench_world_evaluation_only' not in n[0]:return None
 with np.load(p/'trace.npz') as z:
  k=z['stage']=='TASK';tt=z['time_s'][k];ff=z['physical_cuff_force_world_n'][k];mm=z['physical_cuff_moment_world_nm'][k]
 t=np.array([r['time_s'] for r in n]);w=np.asarray([r['cuff_wrench_world_evaluation_only'] for r in n]);use=(t>=tt[0]-1e-9)&(t<=tt[-1]+1e-9);t,w=t[use],w[use]
 assert np.max(abs(np.diff(t)-.00025))<1e-10,'NATIVE_WRENCH_GRID'
 idx=np.clip(np.searchsorted(t,tt),0,len(t)-1);left=np.maximum(0,idx-1);idx=np.where(abs(t[left]-tt)<abs(t[idx]-tt),left,idx);close=abs(t[idx]-tt)<1e-8
 fe=float(np.max(abs(w[idx[close],:3]-ff[close])));me=float(np.max(abs(w[idx[close],3:]-mm[close])));assert fe<1e-8 and me<1e-8,'NATIVE_VS_ORIGINAL_SENSOR_WRENCH_MISMATCH'
 d=dict(id=ident,sampling_s=.00025,sampling_hz=4000,actual_post_step_samples=len(t),force=wrench(t,w[:,:3]),moment=wrench(t,w[:,3:]),original_5ms_overlap=dict(samples=int(close.sum()),force_max_abs_error_N=fe,moment_max_abs_error_Nm=me),JF_JM_definition='UNCHANGED original 5ms left-quadrature for ranking; native stream is added evaluation only',source='original cached interface human_wrench_world already evaluated by original physical step/refresh; never read by candidate generation')
 np.savez_compressed(P/'runtime/motion_series'/(ident+'_NATIVE_WRENCH.npz'),time_s=t,force_world_n=w[:,:3],moment_world_nm=w[:,3:])
 put('analysis/native_wrench/'+ident+'.json',d);print('NATIVE_WRENCH',ident,'4kHz rows',len(t),'overlap error',fe,me,'rateRMS',d['force']['norm_rate']['rms'],flush=True);return d
if __name__=='__main__':
 for ident in sys.argv[1:]:analyze(ident)
