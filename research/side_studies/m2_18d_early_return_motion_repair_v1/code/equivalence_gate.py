from task_bootstrap import *
import numpy as np
def compare(a,b):
 ra=json.loads((STUDY/'output'/(a+'_RESULT.json')).read_text());rb=json.loads((STUDY/'output'/(b+'_RESULT.json')).read_text());ma=ra.get('metric',{});mb=rb.get('metric',{});issues=[];traces={}
 if not(ma.get('valid') and mb.get('valid')):issues.append('TASK_NOT_BOTH_VALID')
 pa=STUDY/'source/results'/a/'trace.npz';pb=STUDY/'source/results'/b/'trace.npz'
 if pa.exists() and pb.exists():
  with np.load(pa) as x,np.load(pb) as y:
   if set(x.files)!=set(y.files):issues.append('TRACE_FIELDS')
   for k in x.files:
    if k not in y or x[k].shape!=y[k].shape:issues.append('TRACE_SHAPE:'+k);continue
    if x[k].dtype.kind in 'fiu':
     same=np.allclose(x[k],y[k],atol=1e-10,rtol=0,equal_nan=True);finite=np.isfinite(x[k])&np.isfinite(y[k]);traces[k]=float(np.max(np.abs(x[k][finite]-y[k][finite]))) if np.any(finite) else 0
    else:same=np.array_equal(x[k],y[k])
    if not same:issues.append('TRACE_DIFFERENCE:'+k)
 else:issues.append('NO_TRACE')
 for key in ('J_F','force_peak','moment_integral','moment_peak','duration_s','physical_clearance'):
  if ma.get(key) is None or mb.get(key) is None or not np.isclose(ma[key],mb[key],atol=1e-10,rtol=0):issues.append('METRIC:'+key)
 selection=[]
 fa=STUDY/'output'/(a+'_SELECTIONS.json');fb=STUDY/'output'/(b+'_SELECTIONS.json')
 if fa.exists() and fb.exists():
  xa=json.loads(fa.read_text())['rows'];xb=json.loads(fb.read_text())['rows']
  if len(xa)!=len(xb):issues.append('DECISION_COUNT')
  for i,(x,y) in enumerate(zip(xa,xb)):
   eq=x['selected_index']==y['selected_index'] and x['selected_source']==y['selected_source'] and np.array_equal(x['applied_plan'],y['applied_plan'])
   accepts=[(r.get('feasible'),r.get('proposal_accepted'),r.get('reason')) for r in x['candidate_records']]==[(r.get('feasible'),r.get('proposal_accepted'),r.get('reason')) for r in y['candidate_records']]
   plans=len(x['candidate_records'])==len(y['candidate_records']) and all(np.array_equal(r['plan'],s['plan']) for r,s in zip(x['candidate_records'],y['candidate_records']))
   if not(eq and accepts and plans):issues.append('CANDIDATE_DECISION:'+str(i))
   selection.append(dict(index=i,chosen_exact=eq,all_candidate_acceptance_exact=accepts,all_plans_exact=plans))
 return dict(baseline=a,optimized=b,status='PASS' if not issues else 'FAIL',issues=issues,trace_max_abs_errors=traces,selection=selection)
def main():
 version=sys.argv[1];pairs=[('002_T0_science_B','010_E1_science_B'),('003_T0_science_M2','011_E1_science_M2'),('004_T0_science_deviation','012_E1_science_deviation')]
 rows=[compare(a,b) for a,b in pairs];out=dict(version=version,status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',rows=rows,tolerance=1e-10,no_tolerance_relaxation=True)
 save(STUDY/'versions'/(version+'_EQUIVALENCE_GATE.json'),out);print(json.dumps(dict(version=version,status=out['status'],issues=[r['issues'] for r in rows])))
if __name__=='__main__':main()
