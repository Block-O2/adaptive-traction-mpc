"""Plot stored GateK contributions; no learner, fit, or physics imports."""
from pathlib import Path
import hashlib
import json
import time
import resource
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P = Path(__file__).resolve().parents[1]
SOURCE = 'families/ppo_reward/continuous_scale_v1/feasibility_counterfactual_v1/context_kernel_diagnostic_v1/diagnostics/GATEK_ONCE_V2/RESULT.json'
EXPECTED = '7c940d3e313379b9f41fd1a2066b624d0c0323998dd5539a675b04c45459cdad'
started, cpu = time.monotonic(), time.process_time()
raw = (P / SOURCE).read_bytes()
assert hashlib.sha256(raw).hexdigest() == EXPECTED
data = json.loads(raw)
stem = P / 'figures/CREDIT_KERNEL_CONTRIBUTIONS_V1'
assert all(not stem.with_suffix(ext).exists() for ext in ('.png', '.pdf', '.svg'))
contexts = ['DEVELOPMENT_HEAVY035', 'DEVELOPMENT_LIGHT065']
fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
for ax, method in zip(axes, ['GLOBAL', 'CONTEXT_LOO']):
    result = data['results'][method]
    for index, context in enumerate(contexts):
        other = contexts[1 - index]
        terms = result['local_cross_first_order_mean_change'][context]
        for offset, value, color in [(-.23, terms[context], '#287c71'), (0, terms[other], '#c56a43'), (.23, result['direct_first_order_mean_change'][context], '#273c68')]:
            ax.bar(index + offset, value * 1e3, width=.21, color=color)
    ax.axhline(0, color='#404040', lw=.7)
    ax.set_xticks([0, 1], ['Heavy', 'Light'])
    ax.set_title('Global batch mean' if method == 'GLOBAL' else 'Context leave-one-out')
    ax.grid(axis='y', alpha=.2)
    ax.set_axisbelow(True)
axes[0].set_ylabel('First-order policy mean change (x 0.001)')
handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in ['#287c71', '#c56a43', '#273c68']]
fig.legend(handles, ['Local context', 'Other context', 'Total'], loc='upper center', ncol=3, frameon=False)
fig.text(.5, .015, 'Fixed old four-row batch; analytic decomposition only. No new physics or generalization evidence.', ha='center', fontsize=9)
fig.tight_layout(rect=(0, .06, 1, .88))
for ext in ('.png', '.pdf', '.svg'):
    fig.savefig(stem.with_suffix(ext), dpi=180, bbox_inches='tight')
plt.close(fig)
manifest = dict(status='PLOTTED_STORED_DIAGNOSTIC_ONLY', source=dict(path=SOURCE, sha256=EXPECTED), script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), outputs={str(stem.with_suffix(ext).relative_to(P)): hashlib.sha256(stem.with_suffix(ext).read_bytes()).hexdigest() for ext in ('.png', '.pdf', '.svg')}, wall_s=time.monotonic()-started, CPU_s=time.process_time()-cpu, peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, learner_calls=0, fit=0, physics=0)
with (P / 'figures/CREDIT_KERNEL_CONTRIBUTIONS_V1_MANIFEST.json').open('x') as f:
    json.dump(manifest, f, indent=2); f.write('\n')
print(json.dumps(manifest))
