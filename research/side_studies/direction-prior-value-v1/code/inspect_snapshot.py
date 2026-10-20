from freeze import *
def main():
 path=STUDY/'output/parent_dev_0_OUTBOUND_2_SNAPSHOT.json';r=json.loads(path.read_text());print(json.dumps(r['opaque_fork_preserved'],indent=2));print(json.dumps(dict(snapshot_bytes=path.stat().st_size,full_native_integration_count=r['native_state_count'])))
if __name__=='__main__':main()
