from freeze import *
import sys
def main():
 version=int(sys.argv[1]) if len(sys.argv)>1 else 1;name='008_streaming_fork_regression' if version==1 else '014_streaming_fork_v2_regression';group='streaming_fork_regression' if version==1 else 'streaming_fork_v2_regression';path=STUDY/'queue'/(name+'.json');assert not path.exists();save(path,dict(id=name,kind='physics',mode='branches',group=group,split='smoke',candidates=1,targets=[['OUTBOUND',0]],seed=2026100600,result_path=str(STUDY/'output'/(name+'_RESULT.json'))));print(name)
if __name__=='__main__':main()
