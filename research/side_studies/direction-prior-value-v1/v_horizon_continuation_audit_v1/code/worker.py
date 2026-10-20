from pathlib import Path
import json,sys,time,traceback,os,random,resource
def main():
 request=json.loads(Path(sys.argv[1]).read_text());start=time.time()
 try:
  from study_common import run,save,sha,STUDY,clean
  import numpy as np
  random.seed(request['seed']);np.random.seed(request['seed'])
  from audit_physics import AuditForkInterface,AttributionInterface
  if request['mode']=='audit_fork':interface=AuditForkInterface(request['case'])
  elif request['mode']=='B_reference':
   from interfaces import TableInterface
   table=np.zeros((2,5,3))
   for i,phase in enumerate(('OUTBOUND','RETURN')):
    for j,row in enumerate(request['prefix'].get(phase,[])):table[i,j]=row
   interface=TableInterface(table)
  else:interface=AttributionInterface(request['condition'],request['seed'],request['prefix'])
  interface.loaded_code_manifest_sha256=sha(STUDY/'CODE_MANIFEST.json')
  metric=run(request['id'],interface)
  if interface.child is not None:os._exit(0)
  result=dict(id=request['id'],status='COMPLETE',metric=metric,inputs=request,wall_seconds=time.time()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
 except BaseException as error:
  result=dict(id=request['id'],status='FAILED',error=str(error),traceback=traceback.format_exc(),inputs=request,wall_seconds=time.time()-start)
  if 'interface' in locals() and interface.child is not None:
   save(interface.child['label']+'_ERROR.json',result);os._exit(1)
 path=Path(request['result_path']);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(clean(result) if 'clean' in locals() else result,indent=2));tmp.replace(path)
 print(json.dumps({k:result.get(k) for k in ('id','status','error','wall_seconds')}),flush=True)
if __name__=='__main__':main()
