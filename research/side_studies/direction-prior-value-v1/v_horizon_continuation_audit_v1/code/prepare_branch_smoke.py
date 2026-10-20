from freeze import *
def main():
 name='005_branch_smoke'
 save(STUDY/'queue'/(name+'.json'),dict(id=name,kind='physics',mode='branches',group='branch_smoke',split='smoke',candidates=2,targets=[['OUTBOUND',0]],result_path=str(STUDY/'output'/(name+'_RESULT.json'))))
 print(name)
if __name__=='__main__':main()
