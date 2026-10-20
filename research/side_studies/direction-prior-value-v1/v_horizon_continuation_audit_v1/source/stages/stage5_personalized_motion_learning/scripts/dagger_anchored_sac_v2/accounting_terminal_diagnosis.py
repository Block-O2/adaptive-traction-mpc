"""Read-only terminal accounting diagnosis; never alters learning state."""
from common import *
def run():
 rows=[]
 for name in ('candidate_attempt_1_point_025000_budget_036283','candidate_attempt_1_point_030000_budget_041283','candidate_attempt_2_point_035000_budget_046283','final_attempt_state'):
  v=torch.load(O/'checkpoints'/name/'resume.pt',map_location='cpu',weights_only=False)
  rows.append(dict(checkpoint=name,updates=v['updates'],actor_updates=v['actor_updates'],sample_counts=v['sample_counts'],keys=list(v),deficit=v['updates']*64-v['sample_counts']['history']))
 save('TERMINAL_ACCOUNTING_DIAGNOSIS.json',dict(rows=rows,no_state_changed=True));print(json.dumps(clean(rows)),flush=True)
if __name__=='__main__':run()
