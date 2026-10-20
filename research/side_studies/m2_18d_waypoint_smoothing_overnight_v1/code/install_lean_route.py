from task_bootstrap import *
import ast
def main():
 events=[json.loads(l) for l in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];ended={r['id'] for r in events if r['event']=='END'};assert not [r['id'] for r in events if r['event']=='START' and r['id'] not in ended],'WAIT_FOR_SINGLE_OWNER_IDLE'
 p=STUDY/'code/worker.py';s=p.read_text();old=" request=json.loads(Path(sys.argv[1]).read_text());start=time.time();sys.meta_path.insert(0,NoPerformanceP())"
 new=old+"\n if request.get('research_profile') is False:\n  import lean_instrumentation\n  lean_instrumentation.prime()"
 assert old in s;s=s.replace(old,new,1);ast.parse(s);p.write_text(s);print('RESEARCH_LEAN_OPTION_READY')
if __name__=='__main__':main()
