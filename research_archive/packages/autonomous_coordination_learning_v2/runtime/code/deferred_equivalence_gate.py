from full_native_equivalence import *
def main():
 ids=['280_E7_DEFERRED_science_B','281_E7_DEFERRED_science_M2','282_E7_DEFERRED_science_deviation'];bases=['002_T0_science_B','003_T0_science_M2','004_T0_science_deviation'];rows=[]
 for a,b in zip(bases,ids):
  row=full_compare(a,b);original=json.loads((STUDY/'source/results'/a/'summary.json').read_text())['qualification']['true_physics'];new=json.loads((STUDY/'source/results'/b/'summary.json').read_text())['qualification']['true_physics'];row['original_true_physics_record_exact']=original==new
  if original!=new:row['issues'].append('ORIGINAL_EVALUATOR_OBSERVER_RECORD_DIFFERENCE');row['status']='FAIL'
  proof=json.loads((STUDY/'output'/(b+'_DEFERRED_EVALUATION.json')).read_text());row['deferred_samples']=sum(r['samples_captured'] for r in proof['rows']);row['all_samples_flushed']=all(r['pending_after_flush']==0 for r in proof['rows']);row['deferred_postprocess_seconds']=sum(r['postprocess_seconds'] for r in proof['rows'])
  if not row['deferred_samples'] or not row['all_samples_flushed']:row['issues'].append('MISSING_DEFERRED_EVALUATION_PROOF');row['status']='FAIL'
  rows.append(row)
 out=dict(version='E7_DEFERRED',status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',rows=rows,tolerance=1e-10,no_tolerance_relaxation=True,scope='Original full B/M2/legal deviation native trajectories, references, selected/candidate decisions, fallback/R2/metrics plus bit-exact original evaluator true_physics aggregate from all original native/boundary samples.',public_B_scheduling_repairs_still_two=True,observer_only=True,source_sha256=sha(STUDY/'code/deferred_evaluation.py'))
 save(STUDY/'versions/E7_DEFERRED_FULL_NATIVE_EQUIVALENCE_GATE.json',out);save(STUDY/'versions/E7_DEFERRED_EQUIVALENCE_GATE.json',out);print(json.dumps(dict(version=out['version'],status=out['status'],rows=[{k:r[k] for k in ('status','issues','native_step_counts','full_native_step_signature_exact','original_true_physics_record_exact','deferred_samples','deferred_postprocess_seconds')} for r in rows])))
if __name__=='__main__':main()
