"""Root follow-through phase, preserving the completed controller milestone."""
from freeze import *
import sys
def main():
 phase=sys.argv[1];state=dict(phase=phase,unix=time.time(),original_start_unix=1791222386,reporting_only=True)
 save(STUDY/'ROOT_PHASE.json',state)
 with (STUDY/'ROOT_PHASE_HISTORY.jsonl').open('a') as handle:handle.write(json.dumps(state)+'\n')
 subprocess.check_call([sys.executable,str(LOCAL/'checkpoint.py'),phase])
if __name__=='__main__':main()
