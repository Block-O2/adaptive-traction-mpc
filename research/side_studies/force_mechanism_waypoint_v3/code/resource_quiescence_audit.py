"""Describe the recorded post-physics runner scope; no leak-proof claim."""
from task_bootstrap import *
import numpy as np

def stats(xs):
 a=np.asarray(xs,dtype=float);return dict(count=len(a),minimum=float(a.min()),p50=float(np.quantile(a,.5)),p95=float(np.quantile(a,.95)),maximum=float(a.max()))

def main():
 events=[json.loads(x) for x in (STUDY/'ATTEMPTS.jsonl').read_text().splitlines() if x.strip()];starts=[x for x in events if x['event']=='START'];ends=[x for x in events if x['event']=='END'];assert len(starts)==len(ends)==159
 last_end=max(x['unix'] for x in ends);rows=[json.loads(x) for x in (STUDY/'output/RESOURCE_LOG.jsonl').read_text().splitlines() if x.strip()];idle=[x for x in rows if x['unix']>=last_end and x.get('owner') is None];assert len(idle)>=20
 windows=[x for x in idle if x.get('windows') and 'commit_headroom' in x['windows']];gib=2**30
 out=dict(status='RECORDED_IDLE_RUNNER_SCOPE',created_unix=time.time(),last_physics_END_unix=last_end,recorded_span_seconds=idle[-1]['unix']-idle[0]['unix'],samples=len(idle),latest_sample_unix=idle[-1]['unix'],idle_runner_and_descendant_PSS_GiB=stats([x['PSS']/gib for x in idle]),idle_owned_process_count=stats([x['owned_count'] for x in idle]),WSL_available_GiB=stats([x['mem_available']/gib for x in idle]),Windows_commit_headroom_GiB=stats([x['windows']['commit_headroom']/gib for x in windows]),Windows_available_GiB=stats([x['windows']['available']/gib for x in windows]),swap_used_MiB=stats([x['swap_used']/2**20 for x in idle]),swap_in_delta_pages=idle[-1]['swap_in']-idle[0]['swap_in'],swap_out_delta_pages=idle[-1]['swap_out']-idle[0]['swap_out'],oom_kill_delta=idle[-1]['oom_kill']-idle[0]['oom_kill'],raw_resource_log_sha256=sha(STUDY/'output/RESOURCE_LOG.jsonl'),interpretation='Observed release/quiescence of the runner plus its verified descendants after all counted physics owners ended. Separately invoked brief read-only helpers are not in this runner-ancestry PSS scope. Shared Windows/WSL availability also reflects unowned activity; this finite window is not a general no-memory-leak proof.',unknown_processes_killed=False,settings_changed=False,physics_attempts_added=0)
 save(STUDY/'reports/RESOURCE_QUIESCENCE_AUDIT.json',out);print(json.dumps({k:out[k] for k in ('status','recorded_span_seconds','samples','idle_runner_and_descendant_PSS_GiB','idle_owned_process_count','swap_in_delta_pages','swap_out_delta_pages','oom_kill_delta')}))
if __name__=='__main__':main()
