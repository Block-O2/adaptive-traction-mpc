from audit_common import *
def main():
 assert not any((STUDY/'output').glob('100_attribution_*_RESULT.json')),'PREREGISTER_BEFORE_ATTRIBUTION_OUTCOMES'
 path=STUDY/'B_REFERENCE_CONTRACT.json';assert not path.exists()
 contract=dict(registered_unix=time.time(),purpose='quantify planner contribution relative to newly measured common B, instead of citing historical B/E',groups=[0,2],complete_attribution_runs_max=10,planned_total_attempts_including_logging_failures_and_B=50,priority='original4 EST/KNOWN pairs and15 fixed-pool candidates first; two B references only if remaining budget allows',algorithm_change=False,no_training=True,B_zero_trace_equivalence_evidence=str(OLD/'FORK_WHOLE_TRACE_AUDIT.json'))
 save(path,contract)
 for group in contract['groups']:
  original=read(STUDY/'queue'/(f'100_attribution_{group}_EST.json'));name=f'110_B_reference_{group}'
  save(STUDY/'queue'/(name+'.json'),dict(id=name,kind='physics',mode='B_reference',group=f'attribution_{group}',seed=original['seed'],prefix=original['prefix'],result_path=str(STUDY/'output'/(name+'_RESULT.json')),contract_sha256=sha(path)))
 print('TWO_B_REFERENCES_PREREGISTERED_BEFORE_ATTRIBUTION')
if __name__=='__main__':main()
