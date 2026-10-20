"""Finite actual wall-physics qualification, after scientific matrix only."""
from task_bootstrap import *
from prepare import enqueue

def main():
 version=sys.argv[1] if len(sys.argv)>1 else 'v1'
 analysis=json.loads((STUDY/('ANALYSIS_'+version+'.json')).read_text())
 assert len(analysis['rows'])>=20,'SCIENTIFIC_MATRIX_FIRST'
 contract=json.loads((STUDY/('MATRIX_CONTRACT_'+version+'.json')).read_text())
 save(STUDY/('WALL_CONTRACT_'+version+'.json'),dict(version=version,frozen_unix=time.time(),execution_mode='REALTIME_CHARACTERIZATION',source='unchanged original B WallPhysicsSession and PlanLifecycle',same_safety=True,delay_rule='new method plans missing native budget are discarded; original native lifecycle independently rejects stale requests and retains existing fallback authority',information='causal commissioned B; physical commissioning and belief can differ under actual wall execution',interpretation='timing/fallback qualification, not a matched scientific J_F ranking; M0 entire native chain is tested',methods=['M0','M1','M2','M3','M4'],weights=contract['weights']))
 for method in ('M0','M1','M2','M3','M4'):
  enqueue(f'070_{version}_wall_{method}',mode='select',group=version+'_actual_wall',method=method,weights=contract['weights'],seed=2026100671,prefix={},algorithm_sources=contract['algorithms'],original=method=='M0',execution_mode='REALTIME_CHARACTERIZATION',delay_replay=method!='M0')
 print('ACTUAL_WALL_QUEUE_READY',version)
if __name__=='__main__':main()
