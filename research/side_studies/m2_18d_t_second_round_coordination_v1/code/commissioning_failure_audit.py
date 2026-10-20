"""All native request stages, including pre-TASK failures; bounded extraction."""
from task_bootstrap import *
from analyze_timing import header_requests
from causal_timing_report import quantile
def main():
 prefix=sys.argv[1] if len(sys.argv)>1 else '09';rows=[]
 for p in sorted((STUDY/'output').glob(prefix+'*_RESULT.json')):
  r=json.loads(p.read_text());id=r['id'];path=STUDY/'source/results'/id/'runtime_artifacts.json.gz';requests=header_requests(path) if path.exists() else []
  stages={}
  for q in requests:stages.setdefault(q['stage'],[]).append(q)
  out=dict(id=id,error=r.get('error'),valid=r.get('metric',{}).get('valid',False),stages={stage:dict(request_count=len(qs),activation_count=sum(q.get('outcome')=='ACTIVATED' for q in qs),activation_age_ms=quantile([q['activation_age_ms'] for q in qs if q.get('activation_age_ms') is not None]),compute_ms=quantile([q['compute_ms'] for q in qs if q.get('compute_ms') is not None]),validation_ms=quantile([q['validation_and_command_construction_ms'] for q in qs if q.get('validation_and_command_construction_ms') is not None]),outcomes=[(q['request_id'],q.get('outcome'),q.get('reason')) for q in qs]) for stage,qs in stages.items()},full_native_requests=requests,attribution='No M2/Q computation before TASK: failures here are public native B/host-clock commissioning evidence.')
  rows.append(out);print(json.dumps({k:out[k] for k in ('id','error','stages')}))
 save(STUDY/'reports'/('COMMISSIONING_FAILURE_AUDIT_'+prefix+'.json'),dict(rows=rows,no_physics_added=True))
if __name__=='__main__':main()
