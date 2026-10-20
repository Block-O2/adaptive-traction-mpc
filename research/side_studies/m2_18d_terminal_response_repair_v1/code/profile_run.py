"""Auxiliary scientific cProfile; never used for host qualification."""
from pathlib import Path
import sys,cProfile,pstats,json
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_terminal_response_repair_v1')
sys.path.insert(0,str(S/'code'))
def main():
 import run_one
 cfg=json.loads(Path(sys.argv[1]).read_text())
 assert cfg['execution_mode']=='SCIENTIFIC_SIMULATION'
 profile=cProfile.Profile()
 try:profile.runcall(run_one.main)
 finally:
  profile.dump_stats(str(S/'output'/(cfg['id']+'.pstats')))
  stats=pstats.Stats(profile)
  rows=[]
  for (file,line,name),(primitive,calls,self_s,cumulative_s,callers) in stats.stats.items():
   rows.append(dict(file=file,line=line,function=name,primitive_calls=primitive,calls=calls,self_s=self_s,cumulative_s=cumulative_s,callers=[dict(file=k[0],line=k[1],function=k[2],counts=list(v) if isinstance(v,tuple) else v) for k,v in callers.items()]))
  (S/'reports'/(cfg['id']+'_PROFILE.json')).write_text(json.dumps(dict(scope='Main process scientific simulation only. Profiler perturbs timing; no host qualification claims. Native unchanged physics and model mathematics.',total_s=stats.total_tt,rows=sorted(rows,key=lambda r:r['cumulative_s'],reverse=True)),indent=2)+'\n')
if __name__=='__main__':main()
