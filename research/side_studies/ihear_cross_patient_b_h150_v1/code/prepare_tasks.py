from task_bootstrap import *
def enqueue(id,**kwargs):
 cfg=dict(id=id,kind='physics',budget_attempts=1,version=1,scientific_version='frozen-B-native-Q-v1',timing_version='T0',mode='select',method='M2',weights=str(STUDY/'weights/frozen_Q_v1'),weights_sha256=sha(STUDY/'weights/frozen_Q_v1/weights.npz'),seed=2026100621,prefix={},result_path=str(STUDY/'output'/(id+'_RESULT.json')),source_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json'));cfg.update(kwargs)
 save(STUDY/'queue'/(id+'.json'),cfg)
def main():
 for id,method,mode in [('000_T0_wall_B','M0','REALTIME_CHARACTERIZATION'),('001_T0_wall_M2','M2','REALTIME_CHARACTERIZATION'),('002_T0_science_B','M0','SCIENTIFIC_SIMULATION'),('003_T0_science_M2','M2','SCIENTIFIC_SIMULATION')]:
  enqueue(id,method=method,execution_mode=mode,original=method=='M0',delay_replay=mode=='REALTIME_CHARACTERIZATION')
 print('FOUR_BASELINE_TRACES_QUEUED')
if __name__=='__main__':main()
