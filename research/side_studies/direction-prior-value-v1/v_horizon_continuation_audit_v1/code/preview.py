from freeze import *
import sys
def main():
 prefix=sys.argv[1];rows=[]
 for p in sorted((STUDY/'output').glob(prefix+'*_RESULT.json')):
  r=json.loads(p.read_text());m=r.get('metric',{});s=STUDY/'output'/(r['id']+'_SEARCH.json');search=json.loads(s.read_text()) if s.exists() else {}
  rows.append(dict(id=r['id'],valid=m.get('valid'),J_F=m.get('J_F'),F_peak=m.get('force_peak'),M_integral=m.get('moment_integral'),M_peak=m.get('moment_peak'),phase=m.get('phase_durations'),native_decisions=len(search.get('rows',[])),total_candidates=sum(len(e['candidates']) for e in search.get('rows',[])),model_calls=search.get('model_calls'),model_schedule_calls=search.get('model_schedule_calls'),full_main_api=m.get('main_model_inverse_dynamics_api_calls')))
 print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
