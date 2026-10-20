from prepare_tasks import *
def main():
 prefix={'OUTBOUND':[[.2,.1,-.1],[.05,.15,.25]]}
 enqueue('004_T0_science_deviation',execution_mode='SCIENTIFIC_SIMULATION',seed=2026100623,prefix=prefix)
 cfg=dict(optimization='same-boundary nominal TerminalSet B decide reuse',classify='EXACT_EQUIVALENT_CANDIDATE_PENDING_REGRESSION',boundary='request id/source capture/full adaptive snapshot hash plus exact planner and numeric argument hash',unchanged='candidate-specific residual _evaluate, mechanics/clearance/tracking; native worker and activation unchanged',regressions=['zero B','frozen M2 nominal','frozen M2 legal deviation'],frozen_Q=True)
 save(STUDY/'versions/E1_CONTRACT.json',cfg)
 enqueue('010_E1_science_B',method='M0',original=True,execution_mode='SCIENTIFIC_SIMULATION',timing_version='E1')
 enqueue('011_E1_science_M2',execution_mode='SCIENTIFIC_SIMULATION',timing_version='E1')
 enqueue('012_E1_science_deviation',execution_mode='SCIENTIFIC_SIMULATION',timing_version='E1',seed=2026100623,prefix=prefix)
 print('E1_THREE_REGRESSIONS_AND_MATCHED_T0_DEVIATION_QUEUED')
if __name__=='__main__':main()
