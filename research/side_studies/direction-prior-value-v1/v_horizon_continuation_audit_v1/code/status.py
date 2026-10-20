from freeze import *
import sys
def main():
 if '--wait' in sys.argv:time.sleep(45)
 rows=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines()];starts=[r for r in rows if r['event']=='START'];ends={r['id']:r for r in rows if r['event']=='END'};active=[r['id'] for r in starts if r['id'] not in ends];resources=STUDY/'output/RESOURCES.jsonl'
 with resources.open('rb') as f:
  f.seek(max(0,resources.stat().st_size-16000));lines=f.read().decode().splitlines();last=json.loads(lines[-1])
 phase_file=STUDY/'ROOT_PHASE.json' if (STUDY/'ROOT_PHASE.json').exists() else STUDY/'CONTROLLER_STATE.json'
 state=json.loads(phase_file.read_text());result_files=sorted((STUDY/'output').glob('*_RESULT.json'),key=lambda p:p.stat().st_mtime);recent=[]
 if '--compact' in sys.argv:
  print(json.dumps(dict(hours=round((time.time()-1791222386)/3600,3),attempts=len(starts),active=active,phase=state['phase'],error=state.get('error'),memory_GiB=round(last['mem_available']/2**30,2),PSS_GiB=round(last['PSS']/2**30,2),swap=[last['swap_in'],last['swap_out']],oom=last['oom_kill'],sample_age_s=round(time.time()-last['unix']))));return
 for p in result_files[-2:]:
  r=json.loads(p.read_text());m=r.get('metric',{});recent.append(dict(id=r['id'],worker=r['status'],valid=m.get('valid'),J_F=m.get('J_F'),wall_s=r.get('wall_seconds')))
 print(json.dumps(dict(elapsed_h=(time.time()-1791222386)/3600,attempts=len(starts),active=active,phase=state['phase'],controller_error=state.get('error'),recent=recent,resource=dict(age_s=time.time()-last['unix'],WSL_available_GiB=last['mem_available']/2**30,owned_PSS_GiB=last['PSS']/2**30,swap_in=last['swap_in'],swap_out=last['swap_out'],oom=last['oom_kill'],windows=last['windows'])),indent=2))
if __name__=='__main__':main()
