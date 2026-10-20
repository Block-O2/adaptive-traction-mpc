from freeze import *
def main():
 contract=json.loads((STUDY/'COMPARISON_v2_final.json').read_text());weights=contract['weights']
 cases=[('normal',None,[['OUTBOUND',0]],2026100801),('deviation',[[[.06,.06,.06],[-.04,-.04,-.04],[0,0,0],[0,0,0],[0,0,0]],[[0,0,0]]*5],[['RETURN',1]],2026100802)]
 path=STUDY/'HELDOUT_SNAPSHOT_CONTRACT.json'
 assert not path.exists();save(path,dict(version=1,weights=weights,cases=cases,split='test',same_state_same_pool_pairs=['P/P+V','P+G/P+G+V'],offline_physical_budget_max=69,continuation='native-certified-committed-K3-suffix-v1',no_test_tuning=True,synergy='B, full verified K3 design and OUT first 1/2/3 native actions then B, all newly measured'))
 for i,(group,table,targets,seed) in enumerate(cases):
  name=f'080_audit_{i}_{group}';save(STUDY/'queue'/(name+'.json'),dict(id=name,kind='physics',mode='audit',group='heldout_audit_'+group,split='test',table=table,targets=targets,seed=seed,weights=weights,result_path=str(STUDY/'output'/(name+'_RESULT.json')),contract_sha256=sha(path)))
if __name__=='__main__':main()
