from gates import *
art=json.loads((S/'results/coordination_research_interface_v1/B_original/summary.json').read_text())
print('summary keys',list(art))
def walk(x):
 if isinstance(x,dict):
  if 'decisions' in x:
   print('decisions',len(x['decisions']))
   for d in x['decisions']:
    print(json.dumps({k:d.get(k) for k in ('phase','decision_request_time_s','selection_mode','executed','reference_boundary_continuity','deadline_wait_physical_intervals')})[:1600])
  for v in x.values():walk(v)
 elif isinstance(x,list):
  for v in x:walk(v)
walk(art)
