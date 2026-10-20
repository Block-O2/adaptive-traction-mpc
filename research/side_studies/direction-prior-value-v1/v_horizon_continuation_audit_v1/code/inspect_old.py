from audit_common import *
def main():
 for name in ('080_audit_0_normal','080_audit_1_deviation','085_known_nonmyopic_synergy','015_parent_dev_0_retry3','020_parent_train_1','130_v2_extra_0_0_P','130_v2_extra_0_2_PV'):
  p=OLD/'output'/(name+'_RESULT.json')
  if p.exists():print(json.dumps(dict(id=name,inputs=read(p)['inputs'])))
 a=read(OLD/'output/130_v2_extra_0_0_P_SEARCH.json');v=read(OLD/'output/130_v2_extra_0_2_PV_SEARCH.json')
 for i,(pr,vr) in enumerate(zip(a['rows'],v['rows'])):
  if i>3:break
  accepted=[r for r in vr['candidates'] if not r['rejected']]
  pbest=min(accepted,key=lambda r:r['prediction']['total_cost']);vbest=min(accepted,key=lambda r:r['score'])
  print(json.dumps(dict(decision=i,context_equal=pr['context']==vr['context'],PV_pool_Pbest=[pbest['generation'],pbest['index']],PV_pool_Vbest=[vbest['generation'],vbest['index']],rank_flip=pbest['plan']!=vbest['plan'],count=vr['count_before'])))
 p=OLD/'output/heldout_audit_normal_OUTBOUND_0_candidate0_DATA.json';r=read(p)
 print(json.dumps(dict(data_keys=list(r),metric_keys=list(r['metric']),value_keys=list(r['value_rows'][0]),child=r['child'])))
if __name__=='__main__':main()
