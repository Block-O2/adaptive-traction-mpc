from freeze import *
def main():
 name='013_encoder_v3_late_gate';path=STUDY/'queue'/(name+'.json');assert not path.exists()
 save(path,dict(id=name,kind='physics',mode='branches',group='encoder_v3_gate',split='smoke',candidates=1,targets=[['RETURN',1]],seed=2026100600,result_path=str(STUDY/'output'/(name+'_RESULT.json'))))
 save(STUDY/'PLAN_AMENDMENT_08_ROW_ENCODER.json',dict(unix=time.time(),before_heldout_tests=True,original_start_unix=1791222386,physics_changes=[],safety_changes=[],changes=['Replace per-row recursive Python JSON iterencode with bounded single-row C encoding; hash bytes remain identical, every history row checked','new cold late RETURN B parent/child regression verifies full fork equality, B cost and unique archive after encoder change'],new_gate_attempts=2,high_fidelity_cap=300,clock_not_reset=True))
 print(name)
if __name__=='__main__':main()
