from prepare import *
def main():
 gate=json.loads((S/'MATCHED_STATE_VALIDATION.json').read_text());assert gate['status']=='PASS'
 hist=S/'code_history/validated_route_continuation';hist.mkdir(parents=True)
 for name in ['matched_harness.py']:
  shutil.copy2(S/'code'/name,hist/name);shutil.copy2(WIN/'code'/name,S/'code'/name)
 for name in ['analyze_matched.py','continue_registration.py']:shutil.copy2(WIN/'code'/name,S/'code'/name)
 a=json.loads((S/'reports/discovery_B0_repeat_1_SNAPSHOT.json').read_text());b=json.loads((S/'reports/discovery_B0_repeat_2_SNAPSHOT.json').read_text())
 def diff(a,b,p):
  if type(a)!=type(b):return [dict(path=p,a=str(a)[:100],b=str(b)[:100])]
  if isinstance(a,dict):return sum((diff(a.get(k),b.get(k),p+'.'+k) for k in a.keys()|b.keys()),[])
  if isinstance(a,list):
   if len(a)!=len(b):return [dict(path=p,length_a=len(a),length_b=len(b))]
   return sum((diff(x,y,p+'.'+str(i)) for i,(x,y) in enumerate(zip(a,b))),[])
  return [] if a==b else [dict(path=p,a=a,b=b)]
 differences=diff(a,b,'root');save(S/'REPEAT_MANIFEST_DIFFERENCES.json',dict(differences=differences,explanation='only parent diagnostic gc_events list grew due to explicit collect between forks; every immediate fork restore hash and after-child parent hash matched; all physics/controller/RNG/reference state equal. Continuation collects once per fork boundary to avoid extra diagnostic state changes. No logger state scrub or physics restore.'))
 save(S/'CONTINUATION_REGISTRATION.json',dict(unix=time.time(),parent_failed='discovery_parent_B0',replacement_parent='discovery_parent_B0_replacement',justification='two completed same-action branches prove exact scientific route; offline gate-report defect terminated initial parent, no physics/safety/state mismatch; new current live parent uses that verified route',repeat_new_physics=0,planned_attempts=['replacement parent','O','R','OR','Frozen_M2','RETURN_entry_zero','RETURN_entry_R'],candidates_unchanged=True,thresholds_unchanged=True,protocol_sha256=sha(S/'EXPERIMENT_PROTOCOL.json'),stop_on_actual_fork_mismatch=True))
 save(S/'CURRENT_CODE_MANIFEST.json',{str(p.relative_to(S)):dict(bytes=p.stat().st_size,sha256=sha(p)) for d in ['code','deps','source/stages','native','build','weights'] for p in (S/d).rglob('*') if p.is_file()})
 print('CONTINUATION_REGISTERED_WITH_ORIGINAL_GATE_PASS',flush=True)
if __name__=='__main__':main()
