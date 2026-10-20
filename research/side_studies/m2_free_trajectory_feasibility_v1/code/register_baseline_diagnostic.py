from explore_common import *
import shutil
def main():
 assert not (S/'BASELINE_REPEAT_PROTOCOL.json').exists()
 p=Path(__file__).parent/'baseline_diagnostic.py';shutil.copy2(p,S/'code/baseline_diagnostic.py')
 save(S/'BASELINE_REPEAT_PROTOCOL.json',dict(registered_unix=time.time(),trigger='Observed discovery RETURN-only gains have substantial pre-intervention OUTBOUND differences and commissioned estimates differ. Trigger derived from exposed discovery, not a new confirmatory hypothesis.',prospective_physical_plan='After all registered discovery/validation, provided no native safety/causal/trace blocker, run exactly two cold B-zero repeats at discovery seed2026100901.',new_attempts_cap=2,total_all_package_attempt_cap=24,seed=2026100901,table='same registered zero table as001_search_B',candidate_selection_influence='NONE; do not change selected candidate, original tolerances or validation conclusions',evaluation='report three B raw full/phase J_F, motion ratios, task entry and commissioning variation; do not subtract a best B or redefine candidate gain',clock='same original REALTIME_CHARACTERIZATION cold native contract',stop='same original physical/causal/trace/wall gate; no retries',basis='research attribution diagnostic within unused registered reserve; exploratory trigger, prospective attempt count/config; not independent candidate validation',script_sha256=sha(S/'code/baseline_diagnostic.py')))
 print('REGISTERED_TWO_BASELINE_REPEATS_NO_RESELECTION',flush=True)
if __name__=='__main__':main()
