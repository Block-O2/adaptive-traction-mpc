from audit_common import *
def main():
 for name in ('CODE_MANIFEST.json','AUDIT_CONTRACT.json','MAIN_SOURCES_BEFORE.json','SOURCE_SEMANTICS.json'):
  data=read(STUDY/name)
  print(name,json.dumps(data)[:10000])
 for pattern in ('*_RESULT.json','*_OUTCOME.json'):
  paths=list((STUDY/'output').glob(pattern))
  for p in paths[:2]:
   d=read(p);print(p.name,'KEYS',list(d));print('metric',json.dumps(d.get('metric'))[:6500]);print('counters',json.dumps({k:v for k,v in d.items() if 'call' in k or 'step' in k or 'wall' in k}))
 print('resources first', (STUDY/'output/RESOURCES.jsonl').read_text().splitlines()[0][:2200])
 print('archives',[p.name for p in (STUDY/'code_history').iterdir()])
if __name__=='__main__':main()
