from common import *
import numpy as np
def main():
 gate=read(NEW/'ORACLE_GATE.json');records={}
 for contract in ('COMMITTED','ROLLING_P'):
  accepted=[r for s in gate['states'] for r in s['rows'] if r['accepted'] and r['qualified']];records[contract]=dict(accepted_candidates=len(accepted),forecast_RMSE_Ns={key:float(np.sqrt(np.mean([(r[key]-r[contract])**2 for r in accepted]))) for key in ('P','V1','ORACLE_'+contract)},macro_pool_forecast_RMSE_Ns={key:float(np.mean([s['comparisons'][contract][name]['forecast_RMSE'] for s in gate['states']])) for key,name in (('P','P'),('V1','P_V1'),('ORACLE','P_ORACLE'))},V2='NOT_TRAINED_GATE_FAILED; no fitted forecast/ranking reported')
 models=dict(ridge=dict(status='NOT_TRAINED',reason='mandatory oracle gate FAIL'),MLP_2x128=dict(status='NOT_TRAINED',reason='mandatory oracle gate FAIL'),training_dataset='NOT_CONSTRUCTED; no TRAIN/DEV/HELDOUT_TEST split created',closed_loop='NOT_RUN_GATE_FAILED',primary_objective='J_F unchanged')
 save(NEW/'V1_V2_COMPARISON.json',dict(contracts=records,models=models,scope='V1 original committed target and weights unchanged; rolling-P truth is a new declared diagnostic comparator, not a redefinition of V1 training labels'))
 print(json.dumps(records))
if __name__=='__main__':main()
