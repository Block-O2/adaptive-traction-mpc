"""Recover 27 omitted statistics batches without model updates or physics."""
from common import *
w=torch.load(O/'checkpoints/last_good_frozen_warm_start/resume.pt',map_location='cpu',weights_only=False);end=torch.load(O/'checkpoints/paused_exception_1791133533/resume.pt',map_location='cpu',weights_only=False);assert w['updates']==20000 and end['updates']==20227
rng=np.random.default_rng();rng.bit_generator.state=w['rng']['sampler'];hist=np.load(O/'HISTORY_RL.npz');im=np.load(O/'IMITATION_ONLY.npz');groups=[np.flatnonzero(im['phase']==p) for p in ('OUTBOUND','HOLD','RETURN')];counts={p:0 for p in ('OUTBOUND','HOLD','RETURN')}
for u in range(20001,20228):
 n=len(w['online'])+max(0,u-20010);hi=rng.integers(len(hist['actions']),size=64);oi=rng.integers(n,size=192)
 if u>20200:
  phases=hist['phase'][hi].tolist()+[str(end['online'][i]['phase']) for i in oi]
  for p in counts:counts[p]+=phases.count(p)
 if u<=20010 or u%10==0:
  for g in groups:rng.choice(g,96)
equal=digest(rng.bit_generator.state)==digest(end['rng']['sampler']);latest=json.loads((L/'CHECKPOINTS.jsonl').read_text().splitlines()[-1]);v=torch.load(Path(latest['path'])/'resume.pt',map_location='cpu',weights_only=False);expected=dict(history=v['updates']*64,online=v['updates']*192);recorded=v['sample_counts'];missing=dict(history=27*64,online=27*192,**counts);corrected={k:recorded[k]+missing[k] for k in recorded}
save('RECOVERED_SAMPLE_ACCOUNTING.json',dict(status='PASS' if equal else 'INCONCLUSIVE',mechanism='Prior progress-loop technical resume used last100-update logged statistics, omitting27 already executed batches. Current saved stats remain unchanged; an independent sampler replays only index generation from warm20000 through20227, including exact anchor-index draws, and verifies end sampler state.',sampler_state_bitwise_equal=equal,omitted_updates=27,omitted_update_range=[20201,20227],omitted_samples=missing,recorded_active_state_counts=recorded,reconstructed_actual_counts=corrected,expected_history_online_counts=expected,no_training_or_RNG_state_modified=True));assert equal,'STATISTICS_RECONSTRUCTION_RNG_MISMATCH';assert all(corrected[k]==expected[k] for k in expected);print(json.dumps(dict(status='PASS',corrected=corrected)))
