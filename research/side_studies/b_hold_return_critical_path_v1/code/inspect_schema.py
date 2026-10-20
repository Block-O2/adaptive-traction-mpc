from task_bootstrap import *
def tree(v,depth=0):
 if depth>3:return type(v).__name__
 if isinstance(v,dict):return {k:tree(x,depth+1) for k,x in v.items()}
 if isinstance(v,list):return dict(length=len(v),first=tree(v[0],depth+1) if v else None)
 return v if isinstance(v,(int,float,bool)) or v is None else str(v)[:100]
def main():
 p=Path(sys.argv[1]);v=json.loads(p.read_text());print(json.dumps(tree(v)))
if __name__=='__main__':main()
