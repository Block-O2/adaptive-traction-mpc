from audit_common import *
def main():
 data=read(STUDY/'HUMAN_MODEL_ATTRIBUTION.json');print(data['summary'])
 for p in data['pairs']:
  same=len(p['selected_candidates']['EST'])==len(p['selected_candidates']['KNOWN']) and all(a['plan_hash']==b['plan_hash'] and a['phase']==b['phase'] and a['counts']==b['counts'] for a,b in zip(p['selected_candidates']['EST'],p['selected_candidates']['KNOWN']))
  print(dict(group=p['group'],EST=p['P_EST_J_F'],KNOWN=p['P_KNOWN_J_F'],all_selected_plans_equal=same,qualified=p['qualified'],failed_controls=[k for k,v in p['controls'].items() if not v],B=None if 'new_B_reference' not in p else {k:v for k,v in p['new_B_reference'].items() if k not in ('metric','controls')},B_J_F=None if 'new_B_reference' not in p else p['new_B_reference']['metric']['J_F']))
if __name__=='__main__':main()
