from pathlib import Path
import json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/b_fast_runtime_completion_v1')
j=json.loads((S/'output/019_N4_V2_C2_science_deviation_TASK_ORIGINAL_REPLAY.json').read_text());diff=[]
def walk(a,b,p):
 if type(a)!=type(b):diff.append((p,str(a)[:100],str(b)[:100]));return
 if isinstance(a,dict):
  for k in a.keys()|b.keys():
   if k not in a or k not in b:diff.append((p+k,str(a.get(k))[:100],str(b.get(k))[:100]))
   else:walk(a[k],b[k],p+k+'.')
 elif isinstance(a,list):
  if len(a)!=len(b):diff.append((p,'length',[len(a),len(b)]))
  else:
   for i,(x,y) in enumerate(zip(a,b)):walk(x,y,p+str(i)+'.')
 elif a!=b:diff.append((p,a,b))
for r in j['rows']:walk(r['actual'],r['expected'],r['phase']+'.')
print('DIFFERENCES',diff[:35],'count',len(diff))
print((S/'code/admission_certificates.py').read_text()[:19000])
print((S/'output/019_N4_V2_C2_science_deviation_TASK_ORIGINAL_PROFILE.txt').read_text()[:9000])
