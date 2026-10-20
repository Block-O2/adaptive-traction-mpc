from freeze import *
def main():
 assert json.loads((STUDY/'STREAMING_FORK_V2_GATE.json').read_text())['status']=='PASS'
 assert json.loads((STUDY/'ENCODER_V3_GATE.json').read_text())['status']=='PASS'
 request=json.loads((STUDY/'queue/011_parent_dev_0.json').read_text());name='015_parent_dev_0_retry3';path=STUDY/'queue'/(name+'.json');assert not path.exists();request.update(id=name,resume_of='011_parent_dev_0',result_path=str(STUDY/'output'/(name+'_RESULT.json')),original_input_sha256=sha(STUDY/'queue/011_parent_dev_0.json'),seed=2026100600);save(path,request);print(name)
if __name__=='__main__':main()
