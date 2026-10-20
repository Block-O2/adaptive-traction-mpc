from freeze import *
import sys
def main():
 name=sys.argv[1];p=STUDY/'queue'/(name+'.json');p.parent.mkdir(exist_ok=True);assert not p.exists(),'TASK_EXISTS'
 config=json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
 save(p,dict(id=name,kind='physics',result_path=str(STUDY/'output'/(name+'_RESULT.json')),**config))
 print(str(p))
if __name__=='__main__':main()
