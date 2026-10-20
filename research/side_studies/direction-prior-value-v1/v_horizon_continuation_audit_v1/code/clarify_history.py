from audit_common import *
def main():
 record=read(STUDY/'SOURCE_SEMANTICS.json');p=STUDY/'SEMANTICS.md'
 if record.get('previous_K3_semantics'):return
 shutil.copy2(STUDY/'SOURCE_SEMANTICS.json',STUDY/'SOURCE_SEMANTICS_initial_before_history_clarification.json');shutil.copy2(p,STUDY/'SEMANTICS_initial_before_history_clarification.md')
 record.update(previous_K3_semantics='last issued/requested K3 proposal from ResidualInterface.apply; no receipt feedback updates interface.previous. It is causal proposal history, not guaranteed executed K3 under rejection/fallback',history_clarification_unix=time.time(),history_clarification_changes_code=False)
 save(STUDY/'SOURCE_SEMANTICS.json',record)
 text=p.read_text().replace('previous actually applied K3','previous issued K3 proposal').replace('previous3K maintained','previous issued3K maintained')
 text+='\n## Source-level history clarification\n\n`ResidualInterface.apply` stores `previous=a` when issuing the graph, before native certification; runtime has no callback assigning an executed residual to `coordination_interface.previous`. Thus this field is **last issued proposal**, not a receipt-proven executed residual. Model terminal history uses the same proposed-row convention. Labels and online inference are consistent with this convention; it does not certify physical execution under rejection/fallback. The previous study remains read-only; this clarification corrects the description, not the algorithm or targets.\n'
 p.write_text(text);print('ISSUED_PROPOSAL_HISTORY_CLARIFIED_NO_CODE_CHANGE')
if __name__=='__main__':main()
