from freeze import *
import sys
def main():
 name='012_P_completion_allowance_regression.json';held=STUDY/'queue_held';held.mkdir(exist_ok=True);source=(STUDY/'queue'/name) if sys.argv[1]=='hold' else held/name;destination=held/name if sys.argv[1]=='hold' else STUDY/'queue'/name
 assert source.resolve().is_relative_to(STUDY.resolve()) and destination.resolve().is_relative_to(STUDY.resolve());assert source.exists() and not destination.exists()
 checksum=sha(source);save(STUDY/'QUEUE_HOLD_STATE.json',dict(action=sys.argv[1],source=str(source),destination=str(destination),sha256=checksum,unix=time.time(),reason='graceful runner operational upgrade while physics owner completes current parent',original_start_unix=1791222386));shutil.move(source,destination);assert sha(destination)==checksum;print(sys.argv[1]+'_QUEUE_OK')
if __name__=='__main__':main()
