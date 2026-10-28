"""Plot only original closed/cached outcome metadata; no models or raw replay."""
from pathlib import Path
import hashlib
import json
import resource
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

P=Path(__file__).resolve().parents[1]
INPUT='analysis/TWO_ORIGINAL_NEW_PARAMETER_COLD_RESULTS_V1.json'
started=time.monotonic();cpu=time.process_time()
data=json.loads((P/INPUT).read_text())
assert data['original_independent_parameter_conditions']==2
rows={row['id']:row for row in data['rows']}
styles=[('B','B','#555555','o'),('LATE_H150','Late H150','#2a9d8f','o'),
        ('EARLY_H150','Early H150','#2873b9','o'),('LATE_PHASE','Late phase','#6b8e23','o'),
        ('EARLY_PHASE','Early phase','#c83f49','x'),('BETA_MEAN_UNIQUE_01','Beta mean = fixed lambda .5','#e58a2b','s')]
fig,axes=plt.subplots(1,2,figsize=(12,5.4),sharex=True,sharey=True)
for ax,group,title in zip(axes,['V8VAL03','V8VAL04'],['Original condition 1: heavy065','Original condition 2: light035']):
    ax.axhline(0,color='#b7bdc4',lw=.8);ax.axvline(0,color='#b7bdc4',lw=.8)
    ax.set_xlim(-45,6);ax.set_ylim(-1,8);ax.grid(alpha=.18)
    ax.set_title(title,fontsize=12,pad=12)
    for tag,label,color,marker in styles:
        row=rows.get(group+'_'+tag)
        if row is None or row['complete'] is not True:
            continue
        marker='o' if row['qualified'] is True and marker=='x' else marker
        if row['qualified'] is False:marker='x'
        ax.scatter(row['delta_JF_vs_own_B'],row['delta_JM_vs_own_B'],c=color,marker=marker,s=62,
                   linewidths=1.5,zorder=3,label=label)
    ax.set_xlabel('Delta JF vs own B [N s]')
axes[0].set_ylabel('Delta JM vs own B [N m s]')
axes[0].text(-42,6.9,'B and HISTORY_B: complete / qualified\nFour non-B recipes: original assertion partial\nBeta mean + axis: NOT_RUN after H gate',
             fontsize=10,va='top',linespacing=1.7,bbox=dict(boxstyle='round,pad=.7',fc='#f4f6f8',ec='#d5dae1'))
axes[0].annotate('B / HISTORY_B',xy=(0,0),xytext=(-16,.8),fontsize=9,
                 arrowprops=dict(arrowstyle='-',color='#777'))
ax=axes[1]
for tag,text,offset in [('EARLY_H150','Early H / lambda1 repeat',(-28,28)),
                       ('LATE_H150','Late H',(18,15)),('LATE_PHASE','Late phase',(-38,-42)),
                       ('EARLY_PHASE','Early phase: motion FAIL',(-55,-18)),
                       ('BETA_MEAN_UNIQUE_01','12 means share lambda .5',(20,-2))]:
    row=rows['V8VAL04_'+tag]
    ax.annotate(text,xy=(row['delta_JF_vs_own_B'],row['delta_JM_vs_own_B']),xytext=offset,
                textcoords='offset points',fontsize=8.5,arrowprops=dict(arrowstyle='-',color='#8e949b',lw=.7))
ax.text(-42,1.6,'lambda0: original assertion partial\nlambda .25 / .75: NOT_RUN',fontsize=9,color='#555',linespacing=1.5)
ax.annotate('B',xy=(0,0),xytext=(-13,10),textcoords='offset points',fontsize=9)
fig.suptitle('Frozen control outcomes: force reduction and moment increase remain separate',fontsize=13,y=.99)
fig.text(.5,.02,'Filled points: original full qualification. Cross: complete motion failure. Partial / NOT_RUN have no cost coordinates.  n = 2 parameter conditions.',ha='center',fontsize=9)
fig.tight_layout(rect=(0,.065,1,.94))
base=P/'figures/TWO_ORIGINAL_PARAMETER_FORCE_MOMENT_V1'
for extension in ['png','pdf','svg']:
    target=base.with_suffix('.'+extension);assert not target.exists();fig.savefig(target,dpi=180)
plt.close(fig)
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
manifest=dict(status='ORIGINAL_CLOSED_METADATA_FIGURE_NO_NEW_EVALUATION',source=sha(Path(__file__)),input=dict(path=INPUT,sha256=sha(P/INPUT)),
              outputs={str(base.with_suffix('.'+e).relative_to(P)):sha(base.with_suffix('.'+e)) for e in ['png','pdf','svg']},
              original_parameter_conditions=2,partial_coordinates_imputed=False,aliases_not_independent_replications=True,
              new_model_fit_scorer_raw_physics_calls=0,wall_s=time.monotonic()-started,CPU_s=time.process_time()-cpu,
              RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
with (P/'figures/TWO_ORIGINAL_PARAMETER_FORCE_MOMENT_V1_MANIFEST.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
print(json.dumps({k:manifest[k] for k in ['status','wall_s','CPU_s','RSS_KiB']}))
