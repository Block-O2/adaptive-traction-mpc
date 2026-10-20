from freeze import *
import sys
def main():
 name=sys.argv[1] if len(sys.argv)>1 else '006_P_search_smoke';p=STUDY/'queue'/(name+'.json');assert not p.exists()
 save(p,dict(id=name,kind='physics',mode='search',method='P',seed=2026100600,split='smoke',result_path=str(STUDY/'output'/(name+'_RESULT.json'))))
 print(name)
if __name__=='__main__':main()
