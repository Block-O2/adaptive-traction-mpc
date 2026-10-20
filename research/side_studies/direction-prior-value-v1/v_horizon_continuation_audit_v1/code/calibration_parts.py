from audit_common import *
import numpy as np
def main():
 data=read(STUDY/'SCORE_DECOMPOSITION.json');rows=[]
 for state in data['states']:
  for r in state['rows']:
   partition=r['near_forecast_error']+r['V_terminal_cost_error']-r['PV_committed_score_error'];assert abs(partition)<1e-7
   rows.append(dict(state=r['state'],index=r['index'],near_error=r['near_forecast_error'],corrected_tail_error=r['V_terminal_cost_error'],P_error=r['P_committed_score_error'],PV_error=r['PV_committed_score_error'],full_model_clock_end_minus_actual_s=r['model_end_vs_actual_end_s'],cost_partition_error=partition,near_interval=[r['physical_start_s'],r['model_split_physical_clock_s']],true_near=r['true_cost_corresponding_model_near_interval'],true_tail=r['true_tail_cost_after_model_clock_split']))
 coverage=read(STUDY/'TERMINAL_FEATURE_COVERAGE.json');nearest=[r['nearest_training_normalized_RMS'] for r in coverage['rows']];events=read(STUDY/'EVENT_CLOCK_ALIGNMENT.json')['rows'];matches=[r for r in events if r['event_match_available']]
 result=dict(rows=rows,online_near_RMSE=float(np.sqrt(np.mean([r['near_error']**2 for r in rows]))),online_corrected_tail_RMSE=float(np.sqrt(np.mean([r['corrected_tail_error']**2 for r in rows]))),nearest_training_normalized_RMS_min_median_max=[min(nearest),float(np.median(nearest)),max(nearest)],max_absolute_full_model_end_clock_error_s=max(abs(r['full_model_clock_end_minus_actual_s']) for r in rows),interpretation='near and corrected-tail errors are signed components of total PV error at the MODEL clock split; this is not the same target as evaluating V at a matched actual-native event, and correlated errors can cancel')
 save(STUDY/'CALIBRATION_PARTITION.json',result);print(json.dumps(result))
if __name__=='__main__':main()
