import pathlib,subprocess,json,time,signal
r=pathlib.Path(__file__).resolve().parents[1];base=r/'runs/dual_maximal_01';base.mkdir(parents=True,exist_ok=False);py=str(r/'.venv/bin/python');processes=[];begin=time.monotonic();commands=[]
try:
 for name,cpu in [('a',0),('b',2)]:
  out='runs/dual_maximal_01/'+name
  cmd=[py,'deployment_audit/measure.py','--out',out,'--','taskset','-c',str(cpu),py,'resource_guard.py','--out',out,'--seconds','600','--',py,'run_rollout.py','--enable','--policy','maximal','--out',out+'/physics']
  commands.append(cmd);processes.append(subprocess.Popen(cmd,cwd=r))
 (base/'DUAL_START.json').write_text(json.dumps({'unix':time.time(),'commands':commands,'physical_cores':[0,1],'logical_cpus':[0,2],'environment_count':2,'wall_cap_s':630},indent=2))
 for proc in processes:proc.wait(timeout=max(1,630-(time.monotonic()-begin)))
finally:
 for proc in processes:
  if proc.poll() is None:
   proc.send_signal(signal.SIGINT)
   try:proc.wait(timeout=30)
   except subprocess.TimeoutExpired:proc.terminate();proc.wait(timeout=5)
 result={'wall_s':time.monotonic()-begin,'returncodes':[p.returncode for p in processes],'all_joined':all(p.poll() is not None for p in processes)}
 (base/'DUAL_END.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
raise SystemExit(0 if all(p.returncode==0 for p in processes) else 1)
