from task_bootstrap import *
def enqueue(id,**kw):
 p=STUDY/'queue'/(id+'.json')
 obj=dict(id=id,kind='physics',version=1,budget_attempts=1,result_path=str(STUDY/'output'/(id+'_RESULT.json')),**kw)
 if p.exists():assert json.loads(p.read_text())==obj
 else:save(p,obj)
def main():
 enqueue('000_original_B',original=True)
 enqueue('001_zero_interface')
 print('BASELINE_QUEUE_READY')
if __name__=='__main__':main()
