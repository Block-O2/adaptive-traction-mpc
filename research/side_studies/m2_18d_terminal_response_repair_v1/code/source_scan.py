from task_bootstrap import *
def main():
 root=Path(sys.argv[1]);patterns=sys.argv[2].split(',');limit=int(sys.argv[3]) if len(sys.argv)>3 else 100;out=[]
 for p in sorted(root.rglob('*.py')):
  for n,line in enumerate(p.read_text(errors='replace').splitlines(),1):
   if any(x in line for x in patterns):out.append(dict(path=str(p),line=n,text=line[:240]))
   if len(out)>=limit:print(json.dumps(out));return
 print(json.dumps(out))
if __name__=='__main__':main()
