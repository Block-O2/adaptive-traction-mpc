"""Retrospective source reconstruction, explicitly labelled; outputs never changed."""
from freeze import *
def main():
 root=STUDY/'source_history/P_SMOKE_FAILED_v0_reconstructed';root.mkdir(parents=True,exist_ok=False)
 p=LOCAL/'planning.py';text=p.read_text()
 text=text.replace(';phase_arrival={};phase_segments=0','').replace(';phase_segments=0;clone.planner.reset_phase()',';clone.planner.reset_phase()')
 text=text.replace('   # Minimum existing receipt/activation ownership tick is physical time,\n   # not compute time. Do not let it vanish in the analytic continuation.\n   phase_segments+=1\n','')
 text=text.replace("    phase_arrival[phase.value]=phase_s+.005*phase_segments\n",'')
 text=text.replace(",predicted_phase_arrival_elapsed_s=phase_arrival,matched_model_feasible=all(t<=9.020+1e-9 for t in phase_arrival.values())",'')
 text=text.replace("     pred=self.predictor.predict(b,c,plan,self.count)\n     if not pred['matched_model_feasible']:raise ValueError('PREDICTED_R2_MATCHED_TIMING_INELIGIBLE:'+str(pred['predicted_phase_arrival_elapsed_s']))\n     delta=", "     pred=self.predictor.predict(b,c,plan,self.count);delta=")
 (root/'planning.py').write_text(text)
 save(root/'PROVENANCE.json',dict(source_reconstructed_from='preserved tool patches and v0 implementation before timing predicate',retrospective=True,original_numeric_results_untouched=True,result_path=str(STUDY/'output/006_P_search_smoke_RESULT.json'),prior_code_manifest_sha256=json.loads((STUDY/'TASK_LEDGER.json').read_text())['006_P_search_smoke']['config'].get('code_manifest_sha256'),exact_original_aggregate_manifest_not_recovered=True,algorithm_difference='v0 lacked predicted R2 timing candidate rejection; failure RETURN 9.385 seconds',reconstructed_source_sha256=sha(root/'planning.py')))
 print(str(root))
if __name__=='__main__':main()
