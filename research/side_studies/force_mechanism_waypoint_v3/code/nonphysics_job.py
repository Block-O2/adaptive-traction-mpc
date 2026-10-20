from task_bootstrap import *
def main():
 job=sys.argv[1];script=STUDY/'code'/sys.argv[2];start=time.time();code=subprocess.call([sys.executable,str(script),*sys.argv[3:]])
 row=dict(id=job,kind='OFFLINE_NO_PHYSICS',start_unix=start,end_unix=time.time(),wall_seconds=time.time()-start,source_sha256=sha(script),returncode=code,physics_attempts=0)
 with (STUDY/'NONPHYSICS_JOBS.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps(row));raise SystemExit(code)
if __name__=='__main__':main()
