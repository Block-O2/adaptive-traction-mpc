"""Post-run plotting only; include the incomplete final checkpoint transparently."""
from pathlib import Path
import csv, json, hashlib, shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/dagger_anchored_sac_v2')
S=Path('/home/hank/coding/adaptive-traction-mpc-side-studies/m2_18d_t_second_round_coordination_v1/source/stages/stage5_personalized_motion_learning')
L=P/'output'; D=S/'docs/dagger_anchored_sac_v2'; O=S/'results/dagger_anchored_sac_v2'
summary=json.loads((L/'SUMMARY_CONTINUATION.json').read_text())
rows=list(csv.DictReader((L/'CONTINUATION_LEARNING_CURVE.csv').open()))
x=[int(r['actual_collection_steps']) for r in rows]
pending=summary['pending_checkpoint_evaluations'][0]
px=summary['final_collection_steps']
fig,axes=plt.subplots(3,1,figsize=(10,10),sharex=True,layout='constrained')
axes[0].plot(x,[float(r['J_F_complete_valid_only']) for r in rows],'o-',label='NATIVE mean: completed checkpoint protocol')
axes[0].plot([x[-1],px],[float(rows[-1]['J_F_complete_valid_only']),pending['J_F']],'--',color='gray')
axes[0].scatter([px],[pending['J_F']],marker='D',color='gray',label='25k NATIVE 2/2 VALID; MATCHED/stochastic pending')
for value,label,color in [(1950.059814,'Frozen student','#8c564b'),(1237.487622,'Original controller','#9467bd'),(1194.062007,'CEM transfer','#2ca02c'),(877.722553,'Fixed hip-leading','#d62728')]:
 axes[0].axhline(value,color=color,ls=':',lw=1,label=label+' (NATIVE VALID)')
axes[0].set_ylabel('J_F (N s)'); axes[0].legend(fontsize=8,loc='lower left')
for phase,color in [('OUTBOUND','#1f77b4'),('HOLD','#ff7f0e'),('RETURN','#2ca02c')]:
 y=[float(r[phase]) for r in rows]
 axes[1].plot(x,y,'o-',color=color,label=phase)
 axes[1].plot([x[-1],px],[y[-1],pending['phase_durations'][phase]],'--D',color=color,alpha=.65)
axes[1].set_ylabel('Phase duration (s)'); axes[1].legend()
axes[2].plot(x,[float(r['mean_drift_RMSE']) for r in rows],'o-',color='#9467bd',label='Mean-action RMSE vs immutable student')
axes[2].set_ylabel('Normalized action drift'); axes[2].set_xlabel('Total collection steps (includes frozen initial 11,283)')
axes[2].legend(fontsize=8); axes[2].annotate('25k drift: see per-evaluation evidence',xy=(px,0),xytext=(px,0.00015),ha='right',fontsize=8,color='gray')
for ax in axes: ax.grid(alpha=.2); ax.set_xlim(10500,37500)
fig.suptitle('Anchored SAC v2: one training seed; paused at 36,283 / 50,000\nDuration savings do not establish a pure coordination gain',fontsize=12)
for ext in ['png','pdf']:
 f=L/('CONTINUATION_LEARNING_CURVE.'+ext); fig.savefig(f,dpi=180); shutil.copy2(f,D/f.name)
plt.close(fig)
report=(L/'DAGGER_ANCHORED_SAC_V2_CONTINUATION_REPORT.md').read_text()
old='![Learning curve](CONTINUATION_LEARNING_CURVE.png)'
new=old+'\n\nThe dashed final point includes the two completed25k NATIVE replays (total36,283); its MATCHED/stochastic protocol is pending. Solid points have completed checkpoint protocols. Drift is plotted through the last fully evaluated checkpoint; per-evaluation drift evidence is retained separately.'
if 'The dashed final point includes' not in report: report=report.replace(old,new)
report=report.replace("actual sampler counts{'history': 2878912, 'online': 8636736, 'OUTBOUND': 4418975, 'HOLD': 3914649, 'RETURN': 3182024}","raw accumulated sampler counts (27-batch accounting omission retained){'history': 2878912, 'online': 8636736, 'OUTBOUND': 4418975, 'HOLD': 3914649, 'RETURN': 3182024}; exact reconstructed actual counts appear below")
for folder in (L,D): (folder/'DAGGER_ANCHORED_SAC_V2_CONTINUATION_REPORT.md').write_text(report)
shutil.copy2(Path(__file__),S/'scripts/dagger_anchored_sac_v2'/Path(__file__).name)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''): h.update(b)
 return h.hexdigest()
lock=json.loads((L/'EVIDENCE_TOOL_LOCK_CONTINUATION.json').read_text());lock['sources'][str(Path(__file__))]=sha(Path(__file__))
for folder in (L,D): (folder/'EVIDENCE_TOOL_LOCK_CONTINUATION.json').write_text(json.dumps(lock,indent=2)+'\n')
manifest={str(p):sha(p) for root in (O,L,D,S/'scripts/dagger_anchored_sac_v2') for p in root.rglob('*') if p.is_file() and p.name not in ('CONTINUATION_ARCHIVE_MANIFEST.json','ARCHIVE_MANIFEST.json')}
for folder in (L,D): (folder/'CONTINUATION_ARCHIVE_MANIFEST.json').write_text(json.dumps(dict(files=manifest,count=len(manifest)),indent=2)+'\n')
print(json.dumps(dict(status='PASS',partial_native_point_included=True,manifest_files=len(manifest),report_sha256=sha(L/'DAGGER_ANCHORED_SAC_V2_CONTINUATION_REPORT.md'))))
