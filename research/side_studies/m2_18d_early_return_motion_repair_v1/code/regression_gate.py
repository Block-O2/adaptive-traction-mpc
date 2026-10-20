from equivalence_gate import compare
from task_bootstrap import *
def main():
 version=sys.argv[1];ids=sys.argv[2:5];assert len(ids)==3
 rows=[compare(a,b) for a,b in zip(['002_T0_science_B','003_T0_science_M2','004_T0_science_deviation'],ids)]
 out=dict(version=version,status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',rows=rows,tolerance=1e-10,no_tolerance_relaxation=True,scope='full native trace all fields, scientific metric including force/moment/clearance/time, chosen plan and full candidate acceptance/rejection; timing diagnostics excluded')
 save(STUDY/'versions'/(version+'_EQUIVALENCE_GATE.json'),out);print(json.dumps(dict(version=version,status=out['status'],issues=[r['issues'] for r in rows])))
if __name__=='__main__':main()
