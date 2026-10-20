from full_native_equivalence import full_compare
from task_bootstrap import *
def main():
 pairs={'E1':['010_E1_science_B','011_E1_science_M2','012_E1_science_deviation'],'E2r1':['025_E2r1_science_B','026_E2r1_science_M2','027_E2r1_science_deviation'],'E3':['030_E3_science_B','031_E3_science_M2','032_E3_science_deviation'],'E2r1_C1':['040_E2r1_C1_science_B','041_E2r1_C1_science_M2','042_E2r1_C1_science_deviation']}
 for version,ids in pairs.items():
  rows=[full_compare(a,b) for a,b in zip(['002_T0_science_B','003_T0_science_M2','004_T0_science_deviation'],ids)];out=dict(version=version,status='PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL',rows=rows,tolerance=1e-10,scope='every native .25ms physical step and commands/contact, native decisions/fallback, full q/dq/ddq trace, all candidate acceptance and scientific metrics; genuine host diagnostic timestamps excluded');p=STUDY/'versions'/(version+'_FULL_NATIVE_EQUIVALENCE_GATE.json')
  if p.exists():shutil.copy2(p,STUDY/'versions'/(version+'_FULL_NATIVE_GATE_HISTORY_'+sha(p)+'.json'))
  save(p,out);print(json.dumps(dict(version=version,status=out['status'],step_exact=[r['full_native_step_signature_exact'] for r in rows])),flush=True)
if __name__=='__main__':main()
