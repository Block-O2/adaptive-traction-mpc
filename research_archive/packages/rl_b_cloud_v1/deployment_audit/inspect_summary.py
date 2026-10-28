import json,pathlib,sys
r=pathlib.Path(sys.argv[1]);p=r/'env/episode_0001/summary.json';x=json.loads(p.read_text())
print('summary_keys',list(x));print(json.dumps({k:v for k,v in x.items() if k in ('status','abort_reason','task','safety_mode_counts','qualification','model_identity','reference_identity')},indent=2)[:18000])
