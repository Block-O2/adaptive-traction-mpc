"""Versioned operational resource guard; no scientific or system configuration changes."""
from pathlib import Path
import os,sys,json,time,subprocess
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2');L=P/'output';D=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_matched_bidirectional_exploration_v1/source/stages/stage5_personalized_motion_learning/docs/dagger_anchored_sac_v2');G=2**30;M=2**20
sys.dont_write_bytecode=True;sys.path.insert(0,str(P.parent/'single_human_sac_memory'));import memory_test_v1 as m

POLICY=dict(version='RESOURCE_POLICY_V2_CONTINUATION_21283',scope='operational resource stop criterion only',scientific_changes=[],system_configuration_changes=[],old_policy='new swap >128 MiB alone stops; MemAvailable<1.5GiB and commit headroom<2GiB also stop',reason='prior swap-only pause occurred at 146.105MiB, WSL available2.654GiB, Windows commit headroom4.849GiB; distinguish stable swapping and evaluation working sets from sustained degradation',sample_interval_s=45,trend_min_samples=3,trend_min_span_s=90,same_lifecycle_only=True,stable_swap_level_alone_never_stops=True,immediate=dict(WSL_available_below_GiB=.75,Windows_commit_headroom_below_GiB=.75,oom_kill_counter_increase=True,allocation_warning_or_process_error='existing exception handler preserves complete state',other_heavy_simulation=True),persistent=dict(low_WSL_available_GiB=1.5,low_commit_headroom_GiB=2.,process_tree_PSS_GiB=6.,owned_process_count_over=12,system_count_growth_over=100),trends=dict(swap_per_interval_min_MiB=16,swap_net_min_MiB=96,rapid_swap_net_min_MiB=256,available_per_interval_decline_min_MiB=64,available_net_decline_min_MiB=256,PSS_net_abnormal_growth_MiB=1024,PSS_growth_with_low_memory_MiB=512),throughput=dict(reference_steps_per_s=12.906312346315916,warning_fraction=.5,severe_fraction=.25,requires_three_online_progress_samples_over_90s=True,warning_needs_swap_or_memory_pressure=True),stop_action='set append-only evidence and pause-request flag; policy boundary saves full state. Already-running independent evaluation finishes evidence before next dispatch. No resource expansion, cache dropping, budget reset or new algorithm.',prior_wall_deadline_unchanged=True)
POLICY.update(version='RESOURCE_POLICY_V2_1_LIFECYCLE_FIX',lifecycle_definition='EVALUATION when evaluate.py child exists; TRAINING_ACTIVE only when multiprocessing spawn physics/planner child exists; otherwise RESTORED_IDLE. Do not compare initial physical allocation with restored-idle working sets.',implementation_correction='v2 classified restored-idle and active physics as TRAINING, causing a false PSS-growth stop at22500 with stable swap7.328MiB and available4.710GiB. Thresholds unchanged; counters/state preserved.')
POLICY.update(version='RESOURCE_POLICY_V2_2_PROCESS_WORKSET_FIX',PSS_same_process_identity_required=True,PSS_isolated_growth_requires_tree_above_GiB=5.25,normal_measured_evaluation_tree_GiB=4.584,implementation_correction='v2.1 compared different cold evaluation process identities. At26283 swap remained7.328MiB and available2.671GiB while tree4.584GiB was within measured normal cold evaluation workload. PSS-only abnormal growth now requires the same root/worker identities and exceeding5.25GiB, or concurrent low headroom for the existing512MiB rule. Global low-memory, OOM, swap-growth and throughput rules unchanged. All spent interactions and saved states preserved.')
POLICY.update(version='RESOURCE_POLICY_V3_STREAMING_LIFECYCLE_36283',isolated_PSS_peak_never_stops=True,throughput_only_never_stops=True,operational_phase_markers=True,reason='User authorized diagnosis and minimal logging/lifecycle repair: end-of-evaluation full JSON conversion/string allocation coexisted with the idle training parent. Stream identical payload fields, join/reap sole physics child, and use sustained pressure rather than a PSS peak.',continued_training_gate='No OOM/allocation error; no sustained swap growth/available decline; no sustained same-training working-set growth; evaluation children released before subsequent physics. Cold evaluation phases and archive allocation are separate. Quiet-mode rate alone is not a stop.',steady_training_PSS_min_samples=5,steady_training_PSS_min_span_s=180,steady_training_PSS_growth_MiB=512,steady_training_PSS_requires_pressure=True,prior_wall_deadline_unchanged=False,wall_authorization='New explicit user instruction resumes the previously stopped campaign from36283 to50000, including final replays. Original start/deadline preserved; separate operational continuation deadline recorded, no scientific config or spent collection change.')

def write(name,v):
 for f in (L,D):
  t=f/(name+'.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(f/name)
def append(name,v):
 for f in (L,D):
  with (f/name).open('a') as h:h.write(json.dumps(v)+'\n')
def rows(name):
 p=L/name
 if not p.exists():return []
 out=[]
 for line in p.read_text().splitlines():
  try:out.append(json.loads(line))
  except json.JSONDecodeError:pass
 return out
def sample(tag,pid=None):
 pid=pid or os.getpid();original=m.os.getpid;m.os.getpid=lambda:pid
 try:proc=m.processes()
 finally:m.os.getpid=original
 mem=m.memfile('/proc/meminfo');win=m.windows();vm=dict(x.split() for x in Path('/proc/vmstat').read_text().splitlines());sw=mem['SwapTotal']-mem['SwapFree'];owned=proc['owned'];phase='EVALUATION' if any(str(P/'evaluate.py') in x['cmd'] for x in owned) else ('TRAINING_ACTIVE' if any('multiprocessing.spawn' in x['cmd'] and 'spawn_main' in x['cmd'] for x in owned) else 'RESTORED_IDLE');gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True).stdout.strip()
 marker=L/'OPERATIONAL_PHASE_36283.json'
 if marker.exists():
  try:phase=json.loads(marker.read_text())['stage']
  except (KeyError,json.JSONDecodeError):pass
 identities=[x['pid'] for x in owned if str(P/'evaluate.py') in x['cmd'] or str(P/'evaluate_operational_v3.py') in x['cmd'] or ('multiprocessing.spawn' in x['cmd'] and 'spawn_main' in x['cmd'])];history=rows('RESOURCE_CONTINUATION.jsonl');row=dict(unix=time.time(),tag=tag,campaign_pid=pid,lifecycle=phase,workset_identity=[pid]+sorted(identities),processes=proc,wsl=mem,windows=win,swap_bytes=sw,gpu=gpu,tree_PSS_bytes=sum(x.get('Pss',0) for x in owned),main_PSS_bytes=next((x.get('Pss',0) for x in owned if x['pid']==pid),0),available_bytes=mem['MemAvailable'],commit_headroom_bytes=win['CommitLimit']-win['CommittedBytes'],oom_kill=int(vm.get('oom_kill',0)))
 reasons=[]
 if row['available_bytes']<.75*G:reasons.append('SEVERE_WSL_MEMORY')
 if row['commit_headroom_bytes']<.75*G:reasons.append('SEVERE_COMMIT_HEADROOM')
 if history and row['oom_kill']>history[0]['oom_kill']:reasons.append('OOM_KILL_COUNTER_INCREASE')
 if proc['other_heavy_python']:reasons.append('OTHER_HEAVY_SIMULATION')
 series=[r for r in history if r['lifecycle']==phase and r['policy_version']==POLICY['version'] and row['unix']-r['unix']<=600 and row['unix']-r['unix']>=35]+[row]
 # Last two time-separated samples, plus current; excludes duplicate boundary measurements.
 chosen=[]
 for r in reversed(series):
  if not chosen or chosen[-1]['unix']-r['unix']>=35:chosen.append(r)
  if len(chosen)==3:break
 a=list(reversed(chosen));trend={}
 if len(a)==3 and a[-1]['unix']-a[0]['unix']>=90:
  ds=[a[i+1]['swap_bytes']-a[i]['swap_bytes'] for i in range(2)];da=[a[i]['available_bytes']-a[i+1]['available_bytes'] for i in range(2)];ps=a[-1]['tree_PSS_bytes']-a[0]['tree_PSS_bytes'];av=a[0]['available_bytes']-a[-1]['available_bytes'];swg=sum(ds);trend=dict(span_s=a[-1]['unix']-a[0]['unix'],swap_deltas_MiB=[v/M for v in ds],available_decline_MiB=av/M,PSS_growth_MiB=ps/M)
  if all(r['available_bytes']<1.5*G for r in a):reasons.append('PERSISTENT_LOW_WSL_AVAILABLE')
  if all(r['commit_headroom_bytes']<2*G for r in a):reasons.append('PERSISTENT_LOW_COMMIT_HEADROOM')
  if all(r['tree_PSS_bytes']>6*G and r['available_bytes']<1.5*G for r in a):reasons.append('PERSISTENT_LARGE_TREE_WITH_LOW_MEMORY')
  if all(r['processes']['owned_count']>12 for r in a):reasons.append('PERSISTENT_OWNED_PROCESS_PROLIFERATION')
  if all(r['processes']['system_count']>history[0]['processes']['system_count']+100 and r['commit_headroom_bytes']<2*G for r in a):reasons.append('SYSTEM_PROCESS_GROWTH_WITH_PRESSURE')
  if min(ds)>=16*M and swg>=256*M:reasons.append('SUSTAINED_RAPID_SWAP_GROWTH')
  elif min(ds)>=16*M and swg>=96*M and (row['available_bytes']<2*G or av>=256*M or ps>=384*M):reasons.append('SUSTAINED_SWAP_GROWTH_WITH_PRESSURE')
  if min(da)>=64*M and av>=256*M and row['available_bytes']<1.5*G:reasons.append('SUSTAINED_AVAILABLE_DECLINE')
  same_identity=all(r.get('workset_identity')==row['workset_identity'] for r in a)
  # Trace accumulation and bounded archive peaks are not evidence of a leak.
  # PSS growth only contributes when corroborated by sustained pressure.
  if same_identity and ps>=512*M and min(ds)>=16*M and (row['available_bytes']<2*G or row['commit_headroom_bytes']<2*G):reasons.append('PSS_GROWTH_WITH_SUSTAINED_SWAP_PRESSURE')
 steady=[r for r in history if r['policy_version']==POLICY['version'] and r['lifecycle']==phase and r.get('workset_identity')==row['workset_identity'] and r['campaign_pid']==pid and 35<=row['unix']-r['unix']<=400]+[row]
 steady=steady[-5:]
 if phase=='TRAINING_ACTIVE' and len(steady)==5 and steady[-1]['unix']-steady[0]['unix']>=180 and all(steady[i+1]['tree_PSS_bytes']>steady[i]['tree_PSS_bytes'] for i in range(4)):
  growth=steady[-1]['tree_PSS_bytes']-steady[0]['tree_PSS_bytes'];pressure=all(r['available_bytes']<1.5*G or r['commit_headroom_bytes']<2*G for r in steady)
  if growth>=512*M and pressure:reasons.append('SUSTAINED_TRAINING_PSS_GROWTH_WITH_PRESSURE')
 progress=rows('WORKFLOW_RESUME.log');progress=[r for r in progress if r.get('status')=='ANCHORED_SAC_ONLINE' and 'steps_per_s' in r][-3:]
 if phase=='TRAINING_ACTIVE' and len(progress)==3 and progress[-1]['updated_unix']-progress[0]['updated_unix']>=90 and row['unix']-progress[-1]['updated_unix']<90:
  rates=[r['steps_per_s'] for r in progress];row['steps_per_s']=rates[-1];reference=POLICY['throughput']['reference_steps_per_s']
  if max(rates)<reference*.5 and (row['available_bytes']<1.5*G or trend.get('swap_deltas_MiB',[0])[0]>64):reasons.append('SUSTAINED_THROUGHPUT_LOSS_WITH_PRESSURE')
 row.update(trend=trend,reasons=reasons,safe=not reasons,policy_version=POLICY['version']);append('RESOURCE_CONTINUATION.jsonl',row)
 if reasons:write('RESOURCE_PAUSE_FLAG_V2.json',dict(unix=row['unix'],reasons=reasons,resource_row=row))
 return row
def check(tag):
 row=sample(tag)
 assert row['safe'],'RESOURCE_POLICY_V2:'+','.join(row['reasons'])
 flag=L/'RESOURCE_PAUSE_FLAG_V2.json';assert not flag.exists(),'RESOURCE_POLICY_V2_ASYNC:'+','.join(json.loads(flag.read_text())['reasons'])

if __name__=='__main__':
 pid=int(sys.argv[1])
 while Path(f'/proc/{pid}').exists():
  try:
   r=sample('CONTINUOUS_OWNER_TREE',pid);print(json.dumps({k:r[k] for k in ('unix','lifecycle','tree_PSS_bytes','available_bytes','swap_bytes','reasons')}),flush=True)
   if not r['safe']:break
  except (FileNotFoundError,ProcessLookupError):break
  except Exception as e:append('RESOURCE_MONITOR_ERRORS.jsonl',dict(unix=time.time(),error=str(e)))
  time.sleep(45)
