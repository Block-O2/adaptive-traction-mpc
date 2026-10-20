"""Quantitative closeout; no simulation and no Git mutation."""
from pathlib import Path
import json,statistics,hashlib,sys,csv,math
ROOT=Path(__file__).parent; OUT=ROOT/'output'; D=OUT/'attempt5'
def load(name):return json.loads((D/name).read_text())
def mean(a):return statistics.mean(a) if a else None
def deep_size(value,seen=None):
    if seen is None:seen=set()
    if id(value) in seen:return 0
    seen.add(id(value));n=sys.getsizeof(value)
    if isinstance(value,dict):n+=sum(deep_size(k,seen)+deep_size(v,seen) for k,v in value.items())
    elif isinstance(value,(list,tuple)):n+=sum(deep_size(v,seen) for v in value)
    return n
def parsed(value):
    if value=='':return None
    if value in ('True','False'):return value=='True'
    try:return json.loads(value)
    except (ValueError,TypeError):return value
def run():
    samples=load('MEMORY_SAMPLES.json');final=load('FINAL_STATE.json');replay=load('REPLAY_ACCOUNTING.json');pres=load('PRESERVATION_AFTER.json')
    prior=[json.loads((OUT/f'attempt{i}/FINAL_STATE.json').read_text()) for i in (2,3,4)]
    prior_episodes=sum(r['episodes'] for r in prior);prior_resets=sum(r['resets'] for r in prior)
    def mib(b):return b/2**20
    def gib(b):return b/2**30
    def main(row,key='Pss'):return row['processes']['owned'][0][key]
    milestones=[]
    for step in (15000,20000,25000,30000):
        r=next(x for x in samples if x['tag']==f'milestone_{step}')
        milestones.append(dict(step=step,main_rss_mib=mib(main(r,'Rss')),main_pss_mib=mib(main(r)),tree_pss_mib=mib(sum(x.get('Pss',0) for x in r['processes']['owned'])),windows_available_gib=gib(r['windows']['AvailableBytes']),windows_commit_gib=gib(r['windows']['CommittedBytes']),windows_commit_headroom_gib=gib(r['windows']['CommitLimit']-r['windows']['CommittedBytes']),wsl_available_gib=gib(r['wsl']['MemAvailable']),wsl_cached_gib=gib(r['wsl']['Cached']),wsl_buffers_mib=mib(r['wsl']['Buffers']),wsl_sreclaimable_mib=mib(r['wsl']['SReclaimable']),swap_mib=mib(r['swap_used_bytes']),gpu=r['torch_gpu'],owned_processes=r['processes']['owned_count'],wsl_processes=r['processes']['system_count'],windows_processes=r['windows']['ProcessCount'],episodes=r['episodes'],resets=r['training_resets'],training_episodes_since_original=prior_episodes+r['episodes'],training_resets_since_original=prior_resets+r['training_resets'],evaluation_resets_so_far=2 if step>=25000 else 0,cumulative_continuation_steps_s=r['continuation_steps_s'],segment_steps_s=r['segment_steps_s'],replay_size=r['replay']['size'],replay_allocated_mib=mib(r['replay']['allocated_array_bytes'])))
    steady=[r for r in samples if r['step'] and r['step']>=15000 and r['step']<=30000 and (r['tag']=='formal_periodic_resource_guard' or r['tag'].startswith('milestone_'))]
    early=[r for r in steady if 15000<=r['step']<20000];late=[r for r in steady if 25000<=r['step']<=30000]
    slopes={}
    for key in ('Rss','Pss','Pss_Anon','Pss_File'):
        slopes[key]=dict(early_mean_mib=mib(mean([main(r,key) for r in early])),late_mean_mib=mib(mean([main(r,key) for r in late])),late_minus_early_mib=mib(mean([main(r,key) for r in late])-mean([main(r,key) for r in early])),min_mib=mib(min(main(r,key) for r in steady)),max_mib=mib(max(main(r,key) for r in steady)))
    post_first=[r for r in steady if 25500<=r['step']<27000]
    post_last=[r for r in steady if 28000<=r['step']<=30000]
    post_eval_drift_mib=mib(mean([main(r,'Pss_Anon') for r in post_last])-mean([main(r,'Pss_Anon') for r in post_first]))
    epochs=[r for r in samples if r['step'] is not None]
    warm=json.loads((OUT/'attempt3/MEMORY_SAMPLES.json').read_text())
    allocation_rows=[]
    for tag in ('before_imports','after_torch_mujoco_imports','after_checkpoint_optimizer_load','after_replay_load','after_initial_reset','milestone_12195','milestone_12196'):
        r=next(x for x in warm if x['tag']==tag)
        allocation_rows.append(dict(tag=tag,rss_mib=mib(main(r,'Rss')),pss_mib=mib(main(r)),anonymous_pss_mib=mib(main(r,'Pss_Anon')),file_pss_mib=mib(main(r,'Pss_File')),gpu_allocated_mib=mib(r['torch_gpu']['allocated']) if r['torch_gpu'] else None,gpu_reserved_mib=mib(r['torch_gpu']['reserved']) if r['torch_gpu'] else None))
    peaks=load('EVALUATION_PEAK_SAMPLES.json')
    peak_tree=max([sum(p.get('Pss',0) for p in r['processes']['owned']) for r in epochs]+[r['tree_pss_bytes'] for r in peaks])
    peak_main=max([main(r,'Rss') for r in epochs]+[next((p.get('Rss',0) for p in r['processes'] if p['pid']==epochs[0]['processes']['owned'][0]['pid']),0) for r in peaks])
    peak_gpu=max(r['torch_gpu']['max_reserved'] for r in epochs if r['torch_gpu'])
    assert final['step']==30000 and final['error'] is None and pres['pass_']
    assert all(r['swap_used_bytes']==0 for r in samples)
    assert all(r['safe'] for r in steady), 'Review transient parked pressure before qualifying'
    assert post_eval_drift_mib<128, 'Potential continuing post-evaluation anonymous-memory growth: inspect before qualifying'
    assert all(r['processes']['owned_count']<=3 for r in steady), 'Growing child-process count'
    assert samples[-1]['processes']['owned_count']<=2, 'Planner still present after close'
    # Conservative process budget includes runtime/evaluation/transient margin.
    training_rows=[{k:parsed(v) for k,v in r.items()} for r in csv.DictReader((D/'SAC_LEARNING_CURVE.csv').open())]
    log_bytes=deep_size(training_rows);bytes_per_episode=log_bytes/max(1,len(training_rows))
    eval_records=[json.loads(p.read_text()) for p in D.glob('EVALUATION_seed_*.json')]
    eval_record_bytes=mean([deep_size(r) for r in eval_records]);episodes_per_step=final['episodes']/(final['step']-13169)
    logging=dict(parsed_training_heap_bytes=log_bytes,approx_bytes_per_episode=bytes_per_episode,approx_bytes_per_eval=eval_record_bytes,observed_episodes_per_step=episodes_per_step,note='Parsed JSON/CSV graph approximation; NumPy action arrays and shared interned keys differ. Not direct live heap measurement. One-step abort scenario is a conservative sensitivity case, not an observed claim.')
    estimates={}
    for n in (300000,500000,1000000):
        expected_logs=n*episodes_per_step*bytes_per_episode+2*(n//25000+1)*eval_record_bytes
        worst_episode_logs=n*bytes_per_episode
        process_budget=math.ceil((peak_tree*1.25+expected_logs*1.25)/(2**28))*2**28
        whole_budget=max(6*2**30,process_budget+int(1.5*2**30))
        estimates[str(n)]=dict(replay_capacity_bytes=replay['allocated_array_bytes'],hypothetical_uncapped_replay_bytes=int(n*replay['bytes_per_transition']),sac_tree_ram_budget_bytes=int(process_budget),whole_wsl_ram_budget_bytes=int(whole_budget),expected_logging_bytes=int(expected_logs),one_step_episode_logging_bytes=int(worst_episode_logs),windows_commit_reserve_bytes=2*2**30,qualification='same100k replay, observed episode cadence, sequential evaluation, no competing heavy host workload; extrapolation, not a long-run measurement; source logging remains linear in episodes')
    repeat=dict(first_evaluation_peak_tree_mib=mib(max(r['tree_pss_bytes'] for r in peaks if r['step']==25000)),repeat_evaluation_peak_tree_mib=mib(max(r['tree_pss_bytes'] for r in peaks if r['step']==30000)),final_gc_pss_mib=mib(main(samples[-1])),final_gc_callbacks=samples[-1]['gc']['callbacks'],final_gc_enabled=samples[-1]['gc']['enabled'])
    assert repeat['repeat_evaluation_peak_tree_mib']<=repeat['first_evaluation_peak_tree_mib']+128,'Repeated evaluation peak still increasing'
    assert repeat['final_gc_callbacks']==0 and repeat['final_gc_enabled'],'GC maintenance lifecycle not restored'
    result=dict(status='SAC_MEMORY_QUALIFIED',root_cause='one-time Python/PyTorch/CUDA/MuJoCo startup/first-update allocations and evaluation high-water plus a Windows-Available-only guard; contemporary host video rendering separately caused real commit pressure',leak_observed=False,allocation_rows=allocation_rows,stability=slopes,post_evaluation_anonymous_drift_mib=post_eval_drift_mib,repeated_evaluation=repeat,logging_accounting=logging,milestones=milestones,peak_main_rss_mib=mib(peak_main),peak_tree_pss_mib=mib(peak_tree),peak_gpu_reserved_mib=mib(peak_gpu),estimates=estimates,final=final,total_training_episodes_since_original=prior_episodes+final['episodes'],total_training_resets_since_original=prior_resets+final['resets'],total_evaluation_resets=4,preservation=pres,limitations=['30k is a bounded leak screen, not proof that every future policy/evaluation workload cannot leak','Original12k samples omitted commit/PSS/cache, so their exact Windows-memory composition cannot be reconstructed','Video rendering pressure was real during this diagnostic; it was awaited, never terminated','Original checkpoint lacked RNG; later pressure-stop checkpoint RNG was restored','SAC checkpoints precede current callback transition storage; original and diagnostic stop offsets are preserved, not fabricated'])
    (OUT/'SAC_MEMORY_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    rows=['|Step|Main RSS / PSS MiB|Tree PSS MiB|Windows Available / Commit / Headroom GiB|WSL Available / Cached GiB|GPU allocated / reserved MiB|Own / WSL / Windows processes|Training episodes / resets since 12194|Current segment cumulative / milestone interval steps/s|Replay stored / allocated MiB|','|---:|---:|---:|---|---|---|---|---|---|---|']
    for r in milestones:
        rows.append(f"|{r['step']}|{r['main_rss_mib']:.1f} / {r['main_pss_mib']:.1f}|{r['tree_pss_mib']:.1f}|{r['windows_available_gib']:.2f} / {r['windows_commit_gib']:.2f} / {r['windows_commit_headroom_gib']:.2f}|{r['wsl_available_gib']:.2f} / {r['wsl_cached_gib']:.2f}|{mib(r['gpu']['allocated']):.2f} / {mib(r['gpu']['reserved']):.2f}|{r['owned_processes']} / {r['wsl_processes']} / {r['windows_processes']}|{r['training_episodes_since_original']} / {r['training_resets_since_original']}|{r['cumulative_continuation_steps_s']:.2f} / {r['segment_steps_s']:.2f}|{r['replay_size']} / {r['replay_allocated_mib']:.2f}|")
    theory=['|Collected transitions|Uncapped arrays MiB|Current100k allocated arrays MiB|','|---:|---:|---:|']
    for n in sorted(replay['theory'],key=int):
        x=replay['theory'][n];theory.append(f"|{n}|{mib(x['uncapped_payload_bytes']):.2f}|{mib(x['current_capacity_allocation_bytes']):.2f}|")
    startup=['|Stage|RSS / PSS MiB|Anonymous / file PSS MiB|GPU allocated / reserved MiB|','|---|---:|---:|---:|']
    for r in allocation_rows:startup.append(f"|{r['tag']}|{r['rss_mib']:.1f} / {r['pss_mib']:.1f}|{r['anonymous_pss_mib']:.1f} / {r['file_pss_mib']:.1f}|{r['gpu_allocated_mib']} / {r['gpu_reserved_mib']}|")
    report=f'''# SAC memory qualification v1

STATUS: SAC_MEMORY_QUALIFIED. Memory-only continuation reached30000; latest model, optimizer, replay and RNG are saved; STOP. No300k run started.

## Root cause and accounting

Replay is not the dominant RAM consumer. Actual buffer: n_envs=1, capacity100000, observation(55)float32, next observation(55)float32, action(2)float32, reward/done/timeout float32. Per transition: (55+55+2+1+1+1)*4 =460 bytes. Six preallocated arrays total46000000 bytes =43.87MiB. Original checkpoint12194 stored12193 transitions because SB3 callback resource-stop happens before the current transition is committed. No transition was invented to repair that offset. Replay loading made all capacity arrays resident, so subsequent collection up to30k had essentially no extra array allocation. Capacity stays100k at300k,500k and1M collected transitions; no buffer shrink is justified.

The original R2 guard required both Windows Available>=2GiB and WSL MemAvailable>=2GiB. At12194 it stopped on Windows1.806GiB despite WSL5.33GiB available and zero swap. It did not measure commit, PSS or cache; therefore that old event alone cannot identify a leak or reconstruct exact cache composition. Versioned startup/first-update samples identify the dominant process allocations. Windows and Linux figures describe overlapping guest/host memory and must not be added together; RSS double-counts shared pages, while the process-tree PSS sum apportions them. WSL Cached/Buffers/SReclaimable is reclaimable memory, with MemAvailable accounting for reclaimability; vmmem working set also includes guest kernel/cache and CUDA host mappings.

The first diagnostic assertion expected replay12194; it failed on the authentic12193 buffer before any update. The next resource-gated attempt stopped before updating. A subsequent first CUDA update grew RSS from~1.43GiB after reset to~1.90GiB, while replay changed by only one460-byte transition. Imports alone increased process PSS by~557MiB; replay load added~44MiB. PyTorch GPU tensor allocations/reservations are measured separately from nvidia-smi driver/context memory. Contemporary Windows video rendering separately drove commit headroom below2GiB; these were real pressure stops and not treated as SAC leaks. Checkpoint12196/update7194/replay12194 and RNG were preserved. Another resumed attempt reached13169/update8166/replay13166, then preserved state on another host-render commit spike. Version2 requires120 seconds of quiet before warm-up and parks simulation collection for transient pressure without advancing physical time, retaining the same pressure budgets; severe or persistent pressure still stops. No unrelated process was stopped. The final continuation resumed13169 to30000. No other heavy simulation or Human side-study was started.

{chr(10).join(startup)}

## Bounded milestones

{chr(10).join(rows)}

Training reset totals include the three preserved resource-pressure attempts; raw attempt5 counters count only the continuous13169-to30000 segment. Evaluations add two resets at25k and two after30k, four in total. Across the full diagnostic since12194 there were {prior_episodes+final['episodes']} completed training episodes and {prior_resets+final['resets']} training resets; total physical resets including evaluations {prior_resets+final['resets']+4}. Partial episodes stopped at resource/budget boundaries account for the reset/completion difference.

![Memory accounting figure](SAC_MEMORY_FIGURE_V1.png)

Full per-process RSS/PSS, anonymous/file PSS, swap/page-in/page-out, pressure, WSL MemAvailable/Cached/Buffers/SReclaimable/Shmem, Windows commit/limit/vmmem/process count, GPU allocated/reserved/max, episode/reset counts and replay arrays are in attempt5/MEMORY_SAMPLES.json. Periodic samples include reset churn;25k performs original frozen-learning NATIVE and MATCHED evaluation, followed by the final30k pair. Sampling is synchronous and included in measured throughput. Original campaign console rates divide total prior+steps by continuation time and are unsuitable for resume throughput; this table uses only new steps since13169, with earlier progress in the preserved attempts.

## Leak assessment and30k stability

Main RSS range during>=15k training: {slopes['Rss']['min_mib']:.1f}–{slopes['Rss']['max_mib']:.1f}MiB. Main PSS range: {slopes['Pss']['min_mib']:.1f}–{slopes['Pss']['max_mib']:.1f}MiB. Early15–20k mean PSS {slopes['Pss']['early_mean_mib']:.1f}MiB, late25–30k mean {slopes['Pss']['late_mean_mib']:.1f}MiB, delta {slopes['Pss']['late_minus_early_mib']:.1f}MiB. PSS anonymous delta {slopes['Pss_Anon']['late_minus_early_mib']:.1f}MiB; file delta {slopes['Pss_File']['late_minus_early_mib']:.1f}MiB. The first full-trace evaluation raises the resident high-water baseline; compare subsequent reset windows rather than calling that first difference a leak. Post-evaluation25.5–27k to28–30k anonymous mean drift is {post_eval_drift_mib:.1f}MiB. No monotonic continuing episode growth is observed. This is bounded evidence; interpret transient peaks against returned baselines and the repeated final evaluation, not max-minus-min alone. The OS observer independently captures live evaluation child counts/peaks in EVALUATION_PEAK_SAMPLES.json; host/guest/process measurements are sequential, not one atomic snapshot.

Repeated evaluation peak:25k {repeat['first_evaluation_peak_tree_mib']:.1f}MiB vs30k {repeat['repeat_evaluation_peak_tree_mib']:.1f}MiB (lower). Final GC PSS {repeat['final_gc_pss_mib']:.1f}MiB; GC enabled and zero retained GC callbacks; planner child removed. The second evaluation cycle did not repeat the first resident-baseline jump. The anonymous high-water could include native allocator fragmentation/reuse; without a live native-heap profiler, that exact breakdown is not established and is not claimed.

Reset creates a fresh owner; close joins its thread and clears runtime capture. runtime finally closes planner lifecycle and removes GC callback; new WallPhysicsSession collects old cycles before disabling GC for the finite active session. GC at final close is diagnostic and no allocator trimming/CUDA empty-cache/swap/RAM expansion/cache dropping is used to manufacture stability. Original learning/evaluation logging remains in use. Source/contract remains byte-identical. Process lifetime observations and GPU allocator trends are in raw samples. No unbounded reset/evaluation/subprocess/trace retention was observed within this test; verify this statement against the trends and post-close samples in the result JSON.

## Memory budget and next step

{chr(10).join(theory)}

Peak observed main RSS {mib(peak_main):.1f}MiB; peak owned-tree PSS {mib(peak_tree):.1f}MiB; GPU max reserved {mib(peak_gpu):.1f}MiB. For300k/500k/1M the conservative SAC-tree budgets are {' / '.join(f'{gib(estimates[str(n)]["sac_tree_ram_budget_bytes"]):.2f}' for n in (300000,500000,1000000))}GiB; whole-WSL allowances are {' / '.join(f'{gib(estimates[str(n)]["whole_wsl_ram_budget_bytes"]):.2f}' for n in (300000,500000,1000000))}GiB, with Windows commit headroom>=2GiB. Budgets include25% above observed evaluation tree peak and projected logging, rounded upward to0.25GiB. The replay stays43.87MiB. Logging graph approximation: {bytes_per_episode:.0f}bytes/episode and {eval_record_bytes:.0f}bytes/evaluation; expected logs at300k/500k/1M are {' / '.join(f'{mib(estimates[str(n)]["expected_logging_bytes"]):.1f}' for n in (300000,500000,1000000))}MiB. This approximation is file-backed, not live heap introspection. Under a one-step-per-episode sensitivity scenario episode logs alone could reach {' / '.join(f'{gib(estimates[str(n)]["one_step_episode_logging_bytes"]):.2f}' for n in (300000,500000,1000000))}GiB: monitoring must remain active, and sustained extreme abort/reset cadence would justify a minimal streaming-log version before extending toward1M. That scenario did not occur in this bounded run; no logger change is needed before300k on the measured cadence.

These are projections under the same capacity, sequential evaluation and no competing heavy workload. Cache is reclaimable and overlaps process file PSS, so budget components are not blindly added as disjoint RSS. This nominal16GiB host /~7.62GiB WSL can support>=300k under the measured resource conditions; simultaneous video-render commit spikes were unsafe and are outside that assertion. Memory qualification does not assert SAC task success or guarantee time-to300k.

The measured evaluations timed out at10s; future successful full-task evaluations can have longer traces. Keep a5–6GiB SAC-tree transient contingency for the unchanged30s task deadline, rather than extrapolating4.5GiB as a guarantee for every future policy. This is a planning allowance, not a measured peak or a change to WSL RAM. Retain the pressure guard and evaluation peak observer for future training; reassess if that contingency is approached. No capacity reduction is indicated by the present data.

Minimal fix: resource policy only. Use Windows commit headroom plus WSL MemAvailable, new swap and other heavy simulation checks; Windows Available alone is a warning. Stop jointly low host/guest memory and preserve state. Existing guard thresholds are prospectively in RESOURCE_POLICY_V1.json. Do not reduce buffer or expand WSL RAM/swap. Next: directly resume the latest30k checkpoint with this versioned guard when training is separately requested; STOP now.

## Preservation and verification

Resume verification records existing Adam/entropy states and step counters before/after environment binding, restored RNG for subsequent pressure-stop continuations, replay shape/dtype/bytes and checkpoint hashes. Final state: {final['step']} steps, {final['updates']} updates, {final['episodes']} completed episodes and {final['resets']} resets in the last continuous segment. Checkpoint: `{final['checkpoint']}`; replay: `{final['replay']}`; RNG plus immutable normalization/configuration/R2 lock snapshots are adjacent. SAVED_BUNDLE_VERIFICATION.json verifies saved ZIP CRC, all optimizer archive members and twelve unchanged SAC configuration fields against the12194 checkpoint. All {pres['preexisting_files_checked']} existing tracked/untracked files and original saved states passed SHA256 preservation; scientific R2 lock, Git index and HEAD are unchanged. No Git mutation or deletion of old files; no reward/action/observation/period/normalization/plant/policy configuration change or side-study launch. Only newly generated evaluation runtime_artifacts.json files were replaced by verified lossless.gz archives through the unchanged existing archival routine.

New files only: scripts/single_human_sac_memory_v1 (memory-only orchestration, read-only peak observer, analysis, plotting and closeout), docs/single_human_sac_memory_v1 (prospective resource policy, complete accounting, preserved failed/pressure attempts, reports and bundle verification), results/single_human_sac_memory_v1 (continued checkpoints/replay/RNG and episode/evaluation evidence), and the Windows single_human_sac_memory mirror. No existing scientific source was edited and nothing was staged.

The4076-file check was made before global memory-state finalization. The separate final closeout verifies all4039 files present at the true user-task start and4075 immutable files from the intermediate bounded-test snapshot. This task's newly created top-level memory STATE.json is intentionally advanced to SAC_MEMORY_QUALIFIED; it did not exist at user-task start. The first closeout recheck initially flagged that own-state update; the scope was corrected to the true startup inventory plus an explicit own-state exception, without exempting any R2 scientific file or saved original model.

Commands: original deployed Python launched memory_test_v1.py in Ubuntu; read-only CIM accounting; installed SB3 buffers/reset/runtime lifecycle inspection; analyze_memory_v1.py closeout. Negative assertion and resource-pressure attempts remain in output/attempt2/attempt3/attempt4 and WSL versioned directories. No .wslconfig was present and no WSL resource setting was written. Report is accompanied by SAC_MEMORY_RESULT.json and full accounting; exact lifecycle conclusions must be bounded to this30k evidence.
'''
    (OUT/'SAC_MEMORY_REPORT_V1.md').write_text(report)
    print(json.dumps(dict(status=result['status'],milestones=milestones,slopes=slopes,peak_tree_pss_mib=mib(peak_tree)),indent=2))
if __name__=='__main__':run()
