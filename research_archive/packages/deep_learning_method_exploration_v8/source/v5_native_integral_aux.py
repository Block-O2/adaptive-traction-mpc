"""Auxiliary cadence sensitivity; never overwrites original JF/JM or rankings."""
from pathlib import Path
import os,sys,json,datetime
os.environ['OPENBLAS_NUM_THREADS']='1';sys.dont_write_bytecode=True
import numpy as np
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def integ(t,x,lo,hi):return float(np.linalg.norm(x[:-1],axis=1)@np.maximum(0,np.minimum(t[1:],hi)-np.maximum(t[:-1],lo)))
rows=[]
for file in sorted((P/'analysis/native_wrench').glob('*.json')):
 ident=file.stem;rp=P/'attempts'/(ident+'_RESULT.json')
 if not rp.exists():continue
 r=json.loads(rp.read_text())
 if not r['complete']:continue
 with np.load(P/'runtime/motion_series'/(ident+'_NATIVE_WRENCH.npz')) as z:t=z['time_s'];f=z['force_world_n'];m=z['moment_world_nm']
 nf=integ(t,f,t[0],t[-1]);nm=integ(t,m,t[0],t[-1]);row=dict(id=ident,original_qualified=r['qualified'],original_JF_5ms=r['JF'],original_JM_5ms=r['JM'],aux_force_integral_native_0p25ms_Ns=nf,aux_moment_integral_native_0p25ms_Nms=nm,original_minus_aux_force_Ns=r['JF']-nf,original_minus_aux_moment_Nms=r['JM']-nm)
 cap=P/'history'/(ident+'_TAIL_CAUSAL.json')
 if cap.exists():
  c=json.loads(cap.read_text());cut=c['captures'].get('0.5');fork=c['fork_physical_s'];row['aux_remaining_force_after_fork_Ns']=integ(t,f,fork,t[-1]);row['aux_remaining_moment_after_fork_Nms']=integ(t,m,fork,t[-1])
  if cut:row['aux_short_force_to_actual_H_Ns']=integ(t,f,fork,cut['physical_s'])
 rows.append(row)
groups=[]
for group in sorted(set(r['id'].split('_')[0] for r in rows if 'aux_remaining_force_after_fork_Ns' in r)):
 valid=[r for r in rows if r['id'].startswith(group+'_') and r['original_qualified'] and 'aux_remaining_force_after_fork_Ns' in r]
 if len(valid)<2:continue
 original=min(valid,key=lambda r:r['original_JF_5ms']);aux=min(valid,key=lambda r:r['aux_remaining_force_after_fork_Ns']);groups.append(dict(group=group,qualified_original_5ms_choice=original['id'],qualified_aux_native_force_choice=aux['id'],choices_match=original['id']==aux['id'],scope='Auxiliary sampling sensitivity only; actual original scorer/qualification and all frozen critic labels remain5ms. No winner is redefined by this table.'))
out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='AUXILIARY_SAMPLING_ANALYSIS_ONLY',rows=rows,tail_group_qualified_force_ranking_sensitivity=groups,maximum_abs_original_minus_aux_force_Ns=max(abs(r['original_minus_aux_force_Ns']) for r in rows),scope='Different numerical cadence of the actual same original simulated interface stream. Native0.25ms quadrature is not a continuous sub-step ground truth, and is not named or substituted as the original JF/JM. Early groups without native wrench retain their5ms measurement limitation.',new_physical_START=0)
(P/'analysis/NATIVE_AUX_INTEGRAL_SAMPLING_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print('AUX_NATIVE_INTEGRALS',len(rows),'TAIL_RANKING_SENSITIVITY',groups)
