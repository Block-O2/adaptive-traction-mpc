"""Read-only offline figures from existing sealed/derived metrics; never load raw physics.
Default scope is development-only. Additional groups need explicit opt-in.
"""
from pathlib import Path
import argparse,csv,json,hashlib,os,sys,time,signal,resource,math,traceback

def digest(b):return hashlib.sha256(b).hexdigest()
def sha(p):return digest(Path(p).read_bytes())
def put(p,d):
 t=p.with_name(p.name+'.writing');t.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(t,p)
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--package',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
 ap.add_argument('--groups',required=True,help='Comma-separated exact groups; no glob or implicit discovery')
 ap.add_argument('--label',default='development-only',help='Figure watermark; default development-only')
 ap.add_argument('--allow-additional-groups',action='store_true',help='Explicit final-main opt-in before reading any group outside four approved development groups')
 ap.add_argument('--qualification-matrix',action='store_true');args=ap.parse_args()
 P=args.package.resolve();O=args.out.resolve();groups=[x.strip() for x in args.groups.split(',') if x.strip()]
 assert groups and len(groups)==len(set(groups)),'GROUP_LIST_EMPTY_OR_DUPLICATE'
 assert all(x.replace('_','').isalnum() and '/' not in x for x in groups),'EXACT_GROUP_NAMES_ONLY'
 approved={'DEVRT03','DEVRC02','DEVPC02','EARLYH01'}
 assert args.allow_additional_groups or set(groups)<=approved,'EXPLICIT_MAIN_OPT_IN_REQUIRED_FOR_ADDITIONAL_OR_FROZEN_GROUPS'
 assert O!=P and O.is_relative_to(P),'OUTPUT_MUST_BE_NEW_SUBDIRECTORY_OF_PACKAGE'
 O.mkdir(parents=True,exist_ok=False) # Deliberately refuse all overwrites, including previous partial runs.
 began=time.time();process=dict(pid=os.getpid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]));(O/'source_snapshot.py').write_bytes(Path(__file__).read_bytes())
 for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
 os.environ.update(PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(O/'mpl_cache'),XDG_CACHE_HOME=str(O/'cache'));sys.dont_write_bytecode=True
 if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
 resource.setrlimit(resource.RLIMIT_CPU,(180,185));resource.setrlimit(resource.RLIMIT_AS,(2*2**30,2*2**30))
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(RuntimeError('FIGURE_WALL_LIMIT')));signal.alarm(600)
 inputs={};loaded={};rows=[];outputs=[];warnings=[];status='RUNNING'
 put(O/'START.json',dict(status=status,process=process,began_unix=began,source_sha256=sha(__file__),groups=groups,label=args.label,new_env=0,new_model=0,new_train=0,new_physics=0,additional_group_opt_in=args.allow_additional_groups))
 class NoScientificRuntime:
  def find_spec(self,fullname,path=None,target=None):
   if fullname.split('.')[0] in ['torch','mujoco','traction_mpc','study_common','campaign_v6','matched_harness','pilot_env','native_rl_env','ready_env','pure_rl_env']:
    raise RuntimeError('FORBIDDEN_SCIENTIFIC_RUNTIME_IMPORT:'+fullname)
   return None
 sys.meta_path.insert(0,NoScientificRuntime())
 def load(rel,required=True):
  f=(P/rel).resolve();assert f.is_relative_to(P),'INPUT_OUTSIDE_PACKAGE'
  if not f.exists():
   if required:raise FileNotFoundError(str(f))
   return None
  if str(f) not in inputs:
   b=f.read_bytes();snapshot=O/'input_snapshot'/f.relative_to(P);snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_bytes(b);inputs[str(f)]=dict(path=str(f),bytes=len(b),sha256=digest(b),snapshot=str(snapshot.relative_to(O)));loaded[str(f)]=json.loads(b)
  return loaded[str(f)]
 def field(d,*keys):
  for k in keys:
   if not isinstance(d,dict) or k not in d:return None
   d=d[k]
  return d
 def text_status(v):return 'NOT_AVAILABLE' if v is None else 'PASS' if v else 'FAIL'
 def write_csv(name,records,columns=None):
  if columns is None:columns=list(dict.fromkeys(k for r in records for k in r))
  with (O/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
   for r in records:w.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')) if isinstance(v,(dict,list)) else '' if v is None else v for k,v in r.items()})
  outputs.append(name)
 try:
  configs={};native={};identities={};pair_criteria={}
  for group in groups:
   cfg=load('experiments/'+group+'.json');configs[group]=cfg
   paired=load('analysis/'+group+'_PAIRED_METRICS.json',False)
   pairrows={r['id']:r for r in paired.get('rows',[])} if paired else {}
   if paired:pair_criteria[group]=paired.get('criterion_frozen');warnings += [group+': paired analysis status '+str(paired.get('status'))+' (snapshot only)'] if paired.get('status')!='COMPLETED' else []
   ident=load('analysis/'+group+'_ACTUAL_ACTION_IDENTITIES.json',False);identities[group]=ident
   identityrows={r['id']:r for r in ident.get('rows',[])} if ident else {}
   if group in approved:assert ident and ident['same_actual_physical_parent'] and ident['same_prefork_trace'],'SAME_GROUP_PARENT_IDENTITY_NOT_VERIFIED:'+group
   for a in cfg.get('actions',[]):
    tag=a['tag'];id=group+'_'+tag;r=load('attempts/'+id+'_RESULT.json',False);n=load('analysis/native_metrics/'+id+'.json',False) if r else None
    pair=pairrows.get(id,{});ii=identityrows.get(id,{})
    if n:native[id]=n
    complete=r.get('complete',False) if r else False;qualified=r.get('qualified') if r else None
    if n and complete:
     assert n['qualified_original']==qualified,'ORIGINAL_QUALIFICATION_DISAGREES:'+id
     assert abs(n['JF']-r['JF'])<1e-8 and abs(n['JM']-r['JM'])<1e-8,'ORIGINAL_COST_IDENTITY:'+id
    q=pair.get('extra_quality_retained');action=r.get('action',a.get('action')) if r else a.get('action')
    action_json=json.dumps(action,sort_keys=True,separators=(',',':'),ensure_ascii=False)
    state='NOT_RUN' if r is None else 'PARTIAL_OR_TASK_FAILURE' if not complete else 'QUALIFIED' if qualified else 'COMPLETE_ORIGINAL_QUALIFICATION_FAIL'
    rows.append(dict(id=id,group=group,tag=tag,status=state,complete=complete,qualified_original=qualified,extra_quality_retained=q,extra_quality_status=text_status(q),JF_N_s=r.get('JF') if r else None,JM_Nm_s=r.get('JM') if r else None,cost_scope='COMPLETE_TASK' if complete else 'PARTIAL_OR_NOT_AVAILABLE_UNRANKED',ranking_eligible=bool(complete and qualified and q is True) if group in ['DEVRT03','DEVRC02','DEVPC02'] else None,ranking_eligibility_contract='Original + frozen extra quality; nominal frontier only' if group in ['DEVRT03','DEVRC02','DEVPC02'] else 'NOT_APPLICABLE: no cost frontier computed for this group',complete_original_qualification_eligible=bool(complete and qualified),failed_requirements=field(r,'motion_vs_B','failed_requirements'),error=r.get('error') if r else None,action_sha256=digest(action_json.encode()),action_json=action_json,native_integration_sha256=ii.get('native_integration_sha256'),prefork_trace_fingerprint=ii.get('actual_prefork_trace_fingerprint'),physical_trace_fingerprint=ii.get('actual_physical_trace_fingerprint'),native_hip_jerk_RMS_deg_s3=field(n,'native_motion','jerk_deg_s3','rms')[0] if field(n,'native_motion','jerk_deg_s3','rms') else None,native_knee_jerk_RMS_deg_s3=field(n,'native_motion','jerk_deg_s3','rms')[1] if field(n,'native_motion','jerk_deg_s3','rms') else None,native_force_norm_rate_RMS_N_s=field(n,'native_force','norm_rate','rms'),native_moment_norm_rate_RMS_Nm_s=field(n,'native_moment','norm_rate','rms'),native_force_vector_rate_RMS_N_s=field(n,'native_force','vector_rate_RMS'),native_moment_vector_rate_RMS_Nm_s=field(n,'native_moment','vector_rate_RMS'),tracking_RMS_deg=field(n,'tracking_RMS_deg'),excursion_deg=field(n,'excursion_deg'),clearance_m=field(n,'clearance'),display_note='Full cost diagnostic only; excluded from eligible frontier/ranking' if complete and not qualified else 'Extra-quality fail is separate from original qualification' if qualified and q is False else ''))
  # Only the already sealed B localization summary is needed; no native/raw/derivative loading.
  past_rel='agent_reviews/past_burden/';past_end=load(past_rel+'END.json');past_manifest=load(past_rel+'OUTPUT_MANIFEST.json');past=load(past_rel+'DECISION_SUMMARY.json')
  assert past_end['status']=='COMPLETE' and past['status']=='PASS' and past['all_frozen_inputs_unchanged'],'PAST_BURDEN_NOT_SEALED'
  assert sha(P/(past_rel+'OUTPUT_MANIFEST.json'))==past_end['output_manifest_sha256'],'PAST_MANIFEST_IDENTITY'
  summary_entry=next(x for x in past_manifest['files'] if Path(x['path']).name=='DECISION_SUMMARY.json')
  assert sha(P/(past_rel+'DECISION_SUMMARY.json'))==summary_entry['sha256'],'PAST_SUMMARY_IDENTITY'
  past_rows=[]
  for label,id in [('Nominal','H150N01_B'),('Light/soft','H150L01_B'),('Heavy/stiff','HSAPP01_B')]:
   r=next(x for x in past['rows'] if x['id']==id)
   for i,signal_name in enumerate(['Hip jerk','Knee jerk','Force norm-rate','Moment norm-rate']):
    past_rows.append(dict(Human=label,id=id,signal=signal_name,native_N=r['native_N'],fork_task_s=r['fork_task_s'],stable_past_cutoff_task_s=r['stable_past_cutoff_task_s'],RMS_units=['deg/s3','deg/s3','N/s','N m/s'][i],stable_past_square_fraction=r['stable_past_square_fractions'][i],cross_fork_square_fraction=r['cross_fork_square_fractions'][i],stable_future_square_fraction=r['stable_future_square_fractions'][i],full_RMS=r['full_RMS'][i],conditional_same_N_RMS_floor=r['conditional_fullN_past_only_RMS_floor'][i],floor_condition=past['floor_conditions']))
  # Record all data + source identities durably before matplotlib/numpy imports or rendering.
  site=Path(sys.prefix)/'lib'/('python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor))/'site-packages'
  library_files=[]
  for f in [site/'matplotlib/__init__.py',site/'matplotlib/pyplot.py',site/'matplotlib/backends/backend_agg.py',site/'matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf',site/'numpy/__init__.py']:
   if f.exists():library_files.append(dict(path=str(f),bytes=f.stat().st_size,sha256=sha(f)))
  pre=dict(status='FROZEN_BEFORE_PLOTTING_IMPORT',process=process,source_sha256=sha(__file__),groups=groups,label=args.label,input_files=list(inputs.values()),plotting_library_files=library_files,original_and_extra_gates_separate=True,metrics='existing unfiltered native JSON only; no derivative/integral recomputation',new_env=0,new_model=0,new_train=0,new_physics=0)
  put(O/'PRECOMPUTE_MANIFEST.json',pre)
  import matplotlib
  matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  from matplotlib.lines import Line2D
  import numpy as np
  plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','savefig.dpi':190})
  def savefig(fig,name):
   fig.savefig(O/(name+'.png'),bbox_inches='tight');fig.savefig(O/(name+'.svg'),bbox_inches='tight');plt.close(fig);outputs.extend([name+'.png',name+'.svg'])
  def stamp(fig,title):fig.suptitle(title+'  |  '+args.label,fontsize=13,fontweight='bold')
  nominal=[r for r in rows if r['group'] in ['DEVRT03','DEVRC02','DEVPC02']]
  plotrows=[];aliases={}
  if nominal:
   assert len({r['native_integration_sha256'] for r in nominal if r['complete']})==1,'NOMINAL_NATIVE_PARENT_DIFFERS'
   assert len({r['prefork_trace_fingerprint'] for r in nominal if r['complete']})==1,'NOMINAL_PREFORK_TRACE_DIFFERS'
   # Deduplicate only exact full action JSON and identity/qualification/cost matches, never proximity in cost.
   seen={}
   for r in nominal:
    if not r['complete'] or r['JF_N_s'] is None or r['JM_Nm_s'] is None:continue
    k=(r['action_json'],r['native_integration_sha256'],r['prefork_trace_fingerprint'])
    if k in seen:
     x=seen[k]
     exact=(x['JF_N_s']==r['JF_N_s'] and x['JM_Nm_s']==r['JM_Nm_s'] and x['qualified_original']==r['qualified_original'] and x['extra_quality_retained']==r['extra_quality_retained'] and x['physical_trace_fingerprint']==r['physical_trace_fingerprint'])
     if exact:aliases[x['id']].append(r['id']);continue
     warnings.append('Same action JSON had nonidentical outcomes/identity; retained separately: '+r['id'])
    else:seen[k]=r
    plotrows.append(r);aliases[r['id']]=[r['id']]
   eligible=[r for r in plotrows if r['ranking_eligible']]
   frontier=[r for r in eligible if not any(s['JF_N_s']<=r['JF_N_s'] and s['JM_Nm_s']<=r['JM_Nm_s'] and (s['JF_N_s']<r['JF_N_s'] or s['JM_Nm_s']<r['JM_Nm_s']) for s in eligible)]
   frontier.sort(key=lambda r:r['JF_N_s'])
   for r in rows:r['nominal_eligible_frontier']=any(r['id'] in aliases[x['id']] for x in frontier) if r in nominal else None
   fig,axes=plt.subplots(1,2,figsize=(13,6.2));stamp(fig,'Nominal S1: full-task force and moment cost')
   special={'B':('B',(6,8)),'BLEND':('BLEND',(8,8)),'V6PHASE':('V6PHASE',(7,9)),'SHARED_GP_QUAD':('GP = quadratic (shared action)',(8,18)),'TRAD_COMBO':('TRAD combo',(8,-20))}
   for ax in axes:
    for r in plotrows:
     x,y=r['JF_N_s'],r['JM_Nm_s'];tag=r['tag']
     if not r['qualified_original']:ax.scatter(x,y,marker='x',c='#949aa0',s=45,zorder=2)
     elif r['extra_quality_retained'] is False:ax.scatter(x,y,marker='D',facecolors='none',edgecolors='#bd7029',s=62,linewidths=1.4,zorder=3)
     elif r['extra_quality_retained'] is None:ax.scatter(x,y,marker='s',facecolors='none',edgecolors='#777777',s=45,zorder=3)
     else:ax.scatter(x,y,marker='*' if tag in ['SHARED_GP_QUAD','TRAD_COMBO'] else 'o',c='#8157ad' if tag=='SHARED_GP_QUAD' else '#1b8068' if tag=='TRAD_COMBO' else '#236d9b',s=140 if tag in ['SHARED_GP_QUAD','TRAD_COMBO'] else 38,zorder=4)
    if frontier:ax.plot([r['JF_N_s'] for r in frontier],[r['JM_Nm_s'] for r in frontier],color='#236d9b',lw=.9,alpha=.65,zorder=1)
    ax.set_xlabel('JF: force integral (N s)');ax.set_ylabel('JM: moment integral (N m s)');ax.grid(alpha=.18)
    ax.ticklabel_format(useOffset=False,axis='both')
   axes[0].set_title('Broad view: every complete development action')
   focus=[r for r in plotrows if r['tag'] in ['V6PHASE','SHARED_GP_QUAD','TRAD_COMBO']]
   if focus:
    xs=[r['JF_N_s'] for r in focus];ys=[r['JM_Nm_s'] for r in focus];dx=max(max(xs)-min(xs),.01);dy=max(max(ys)-min(ys),.005)
    axes[1].set_xlim(min(xs)-.35*dx,max(xs)+.7*dx);axes[1].set_ylim(min(ys)-.5*dy,max(ys)+.7*dy)
   axes[1].set_title('Local zoom: descriptive micro-differences')
   for j,ax in enumerate(axes):
    for r in plotrows:
     if r['tag'] not in special or (j==0 and r['tag'] not in ['B','BLEND']):continue
     x,y=r['JF_N_s'],r['JM_Nm_s'];xmin,xmax=ax.get_xlim();ymin,ymax=ax.get_ylim()
     if xmin<=x<=xmax and ymin<=y<=ymax:
      label,offset=special[r['tag']];ax.annotate(label,(x,y),xytext=offset,textcoords='offset points',fontsize=8,arrowprops=dict(arrowstyle='-',lw=.5,color='#666666'))
   handles=[Line2D([],[],marker='o',ls='',color='#236d9b',label='Original + extra quality pass'),Line2D([],[],marker='D',ls='',markerfacecolor='none',color='#bd7029',label='Original pass; extra quality fail (B / BLEND retained)'),Line2D([],[],marker='x',ls='',color='#949aa0',label='Original qualification fail (not on frontier)'),Line2D([],[],color='#236d9b',lw=.9,label='Nondominated observed eligible set')]
   fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.055),ncol=2,frameon=False,fontsize=9)
   fig.text(.5,.015,'No weighted score; no significance/uncertainty claim. All rows and action aliases remain in CSV.',ha='center',fontsize=8)
   fig.tight_layout(rect=(0,.19,1,.93));savefig(fig,'01_nominal_JF_JM_broad_zoom')
   write_csv('01_nominal_all_attempts.csv',nominal);write_csv('01_nominal_plot_aliases.csv',[dict(plotted_id=x['id'],aliases=aliases[x['id']],action_sha256=x['action_sha256'],eligible=x['ranking_eligible'],frontier=x in frontier) for x in plotrows])
  heavy=[r for r in rows if r['group']=='EARLYH01'];heavyshown=[]
  if heavy:
   for tag in ['B','LATE_H150','EARLY_H150']:
    r=next(x for x in heavy if x['tag']==tag);assert r['complete'] and r['qualified_original'],'HEAVY_DISPLAY_ARM_NOT_QUALIFIED:'+tag
    assert r['id'] in native,'HEAVY_NATIVE_METRICS_MISSING:'+tag;heavyshown.append(r)
   names=['B','Late H150','Early H150'];colors=['#677987','#d1983f','#268976']
   metrics=[('native_hip_jerk_RMS_deg_s3','Hip jerk RMS (deg/s3)'),('native_knee_jerk_RMS_deg_s3','Knee jerk RMS (deg/s3)'),('native_force_norm_rate_RMS_N_s','Force-norm rate RMS (N/s)'),('native_moment_norm_rate_RMS_Nm_s','Moment-norm rate RMS (N m/s)')]
   fig,axes=plt.subplots(2,2,figsize=(10.5,7));stamp(fig,'Heavy/stiff: matched qualified native quality')
   for ax,(key,title) in zip(axes.flat,metrics):
    values=[r[key] for r in heavyshown];assert all(x is not None for x in values),'MISSING_EXISTING_NATIVE_METRIC'
    bars=ax.bar(names,values,color=colors,width=.65)
    ax.set_title(title);ax.set_ylim(0,max(values)*1.2);ax.grid(axis='y',alpha=.18)
    for b,v in zip(bars,values):ax.text(b.get_x()+b.get_width()/2,v+max(values)*.025,f'{v:.2f}',ha='center',fontsize=9)
   fig.text(.5,.015,'NO_T5 arms fail original qualification: full evidence in CSV, excluded from cost ranking. No all-metrics claim.',ha='center',fontsize=8)
   fig.tight_layout(rect=(0,.045,1,.94));savefig(fig,'02_heavy_native_jerk_wrench')
   fig,ax=plt.subplots(figsize=(9,2.9));ax.axis('off');stamp(fig,'Heavy/stiff: separate complete-task costs')
   table=ax.table(cellText=[[name,f"{r['JF_N_s']:.6f}",f"{r['JM_Nm_s']:.6f}",'PASS'] for name,r in zip(names,heavyshown)],colLabels=['Policy','JF (N s)','JM (N m s)','Original qualification'],cellLoc='center',loc='center');table.auto_set_font_size(False);table.set_fontsize(10);table.scale(1,1.7)
   fig.text(.5,.04,'Force and moment are separate objectives. Failed NO_T5 costs are retained in CSV and are not successful low-cost solutions.',ha='center',fontsize=8);savefig(fig,'02_heavy_separate_JF_JM_table')
   write_csv('02_heavy_all_five_attempts.csv',heavy)
  fig,axes=plt.subplots(1,2,figsize=(13,5.5));stamp(fig,'Burden already incurred before the OUT1 fork')
  human=['Nominal','Light/soft','Heavy/stiff'];signals=['Hip jerk','Knee jerk','Force norm-rate','Moment norm-rate'];colors=['#3177a6','#d2933b','#528f78','#8f6cab'];x=np.arange(3);width=.19
  for i,sig in enumerate(signals):
   rr=[next(r for r in past_rows if r['Human']==h and r['signal']==sig) for h in human];vals=[100*r['stable_past_square_fraction'] for r in rr]
   bars=axes[0].bar(x+(i-1.5)*width,vals,width,color=colors[i],label=sig)
   for b,v in zip(bars,vals):axes[0].text(b.get_x()+b.get_width()/2,v+.8,f'{v:.1f}',ha='center',fontsize=7,rotation=90)
  axes[0].set_xticks(x,human);axes[0].set_ylim(0,110);axes[0].set_ylabel('Support-safe past share of full sum of squares (%)');axes[0].set_title('Existing unfiltered signals; fork at task 1.70 s');axes[0].grid(axis='y',alpha=.18);axes[0].legend(fontsize=8,frameon=False)
  # Plot precomputed conditional floor/full-RMS ratio, keeping units separate in CSV.
  for i,sig in enumerate(signals):
   rr=[next(r for r in past_rows if r['Human']==h and r['signal']==sig) for h in human]
   vals=[100*r['conditional_same_N_RMS_floor']/r['full_RMS'] for r in rr]
   axes[1].bar(x+(i-1.5)*width,vals,width,color=colors[i])
  axes[1].set_xticks(x,human);axes[1].set_ylim(0,110);axes[1].set_ylabel('Existing conditional RMS floor / full RMS (%)');axes[1].set_title('Conditional bound: same N and unchanged stable past');axes[1].grid(axis='y',alpha=.18)
  fig.text(.5,.015,'Bound is conditional, not an attainable control optimum, safety certificate, comfort claim, or guard-causality proof.',ha='center',fontsize=8)
  fig.tight_layout(rect=(0,.05,1,.93));savefig(fig,'03_prefork_burden_and_conditional_floor');write_csv('03_past_burden_sealed_B_rows.csv',past_rows)
  write_csv('all_selected_groups_qualification_and_metrics.csv',rows)
  if args.qualification_matrix:
   tags=list(dict.fromkeys(r['tag'] for r in rows));fig,ax=plt.subplots(figsize=(max(9,len(tags)*1.2),max(3,len(groups)*.7+1.8)));ax.axis('off');stamp(fig,'Original qualification by exact frozen group')
   lookup={(r['group'],r['tag']):r for r in rows};cells=[];cellcolors=[]
   for group in groups:
    vals=[];cols=[]
    for tag in tags:
     r=lookup.get((group,tag));state=r['status'] if r else 'NOT_PLANNED';label={'QUALIFIED':'PASS','COMPLETE_ORIGINAL_QUALIFICATION_FAIL':'MOTION/QUAL FAIL','PARTIAL_OR_TASK_FAILURE':'PARTIAL/FAIL','NOT_RUN':'NOT RUN','NOT_PLANNED':'-'}[state];vals.append(label);cols.append('#d4eadd' if state=='QUALIFIED' else '#f3ddd1' if state.endswith('FAIL') or 'FAILURE' in state else '#eeeeee')
    cells.append(vals);cellcolors.append(cols)
   tab=ax.table(cellText=cells,cellColours=cellcolors,rowLabels=groups,colLabels=tags,loc='center',cellLoc='center');tab.auto_set_font_size(False);tab.set_fontsize(8);tab.scale(1,1.8);savefig(fig,'04_explicit_groups_qualification_matrix')
  captions='''# 离线研究图说明\n\n本目录是已有指标的可重建快照，标签：**LABEL**。没有运行环境、模型rollout、训练或新物理；未重算积分、导数、滤波或裁剪信号。开发图不等于最终报告或独立验证。\n\n1. 名义S1图合并指定三组同实际native父/同prefork轨迹。灰x为完整但原资格失败，只作成本诊断，不入前沿；空心菱形为原资格通过但额外quality失败，B与BLEND保留。蓝色前沿只使用原资格和额外quality均通过的观测点；不构造加权分数，不把连线解释成已测试连续解。GP和quadratic是同一proposal/物理点；TRAD combo单独标记。所有attempt均保留CSV，只有完整action JSON、父状态、资格、精确成本和physical trace一致才合并绘图别名，不按成本近似合并。局部zoom的微小差异不代表统计显著、误差界或独立学习增量。\n\n2. Heavy图只画B/LATE_H150/EARLY_H150三个原资格通过方案的既有native raw jerk及wrench norm-rate RMS。JF与JM分列，不能概括为所有指标改善。两个NO_T5完整失败的动作、成本和失败原因保留CSV，未作低成本成功排名。\n\n3. Past burden直接读取封存的三Human B摘要。左图是support-safe fork前sum-of-squares份额，cross-fork与future在CSV另列；右图仅把已有同N条件RMS floor除以已有full RMS以显示比例。原floor数值、不同物理单位、native N和cutoff完整保留CSV。下界仅在相同N、past保持不变及原导数support划分下成立；不是可达到的控制最优、安全/舒适证明，也不能证明guard导致峰值。\n\n可选资格矩阵只读取调用者明确列出的组，缺失结果为NOT RUN，partial/原资格失败分别标记。额外/冻结测试组默认拒绝读取；必须主Agent最终显式列出组并使用allow开关。此builder不自动打开PFXV或short_segments。\n\nsource/input SHA和PID身份在绘图库导入前记录于PRECOMPUTE_MANIFEST；输入变化会使封包失败。实际读取的JSON另存input_snapshot，执行source存source_snapshot.py，便于重建本次开发快照；这不把后续变化中的输入冒称最终数据。CSV的ranking_eligible仅适用于名义组额外quality前沿，其他组留空并明确NOT_APPLICABLE；complete_original_qualification_eligible单独保留所有组的完整原资格。所有文件位于新输出目录，重复目录一律拒绝。\n'''.replace('LABEL',args.label)
  captions+='\n本次exact groups：`'+','.join(groups)+'`。\n\n输入快照限制：\n'+''.join('- '+w+'\n' for w in warnings)
  (O/'README_zh.md').write_text(captions);outputs.append('README_zh.md')
  assert all(sha(f)==r['sha256'] for f,r in inputs.items()),'INPUT_CHANGED_DURING_RENDER'
  assert sha(__file__)==pre['source_sha256'],'BUILDER_SOURCE_CHANGED'
  status='PASS';put(O/'BUILD_RESULT.json',dict(status=status,groups=groups,label=args.label,rows=len(rows),nominal_unique_plotted_actions=len(plotrows),nominal_aliases=aliases,heavy_qualified_plotted=[r['id'] for r in heavyshown],paired_criteria=pair_criteria,past_floor_condition=past['floor_conditions'],outputs=outputs,warnings=warnings,versions=dict(matplotlib=matplotlib.__version__,numpy=np.__version__,python=sys.version),input_hashes_unchanged=True,reading_mode='explicit groups only; four-group development allowlist unless explicit main opt-in',new_env=0,new_model=0,new_train=0,new_physics=0,new_integral_or_derivative_recomputation=0,weighted_score_created=False))
 except BaseException as e:
  status='FAILED_RETAINED';put(O/'BUILD_FAILURE.json',dict(status=status,error=f'{type(e).__name__}:{e}',traceback=traceback.format_exc(),all_partial_outputs_retained=True));raise
 finally:
  signal.alarm(0);usage=resource.getrusage(resource.RUSAGE_SELF)
  put(O/'OWNED_PROCESS_AUDIT.json',dict(state='EXITING_NO_CHILDREN',process=process,children=[],persistent_workers=0))
  files={str(f.relative_to(O)):dict(bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(O.rglob('*')) if f.is_file() and 'mpl_cache' not in f.parts and 'cache' not in f.parts and f.name not in ['OUTPUT_MANIFEST.json','END.json']}
  put(O/'OUTPUT_MANIFEST.json',dict(status=status,files=files))
  put(O/'END.json',dict(status=status,process=process,wall_s=time.time()-began,cpu_user_s=usage.ru_utime,cpu_system_s=usage.ru_stime,peak_rss_KiB=usage.ru_maxrss,groups=groups,label=args.label,source_sha256=sha(__file__),manifest_sha256=sha(O/'OUTPUT_MANIFEST.json'),new_env=0,new_model=0,new_train=0,new_physics=0,persistent_workers=0))
  print(json.dumps(dict(status=status,out=str(O),groups=groups,label=args.label,wall_s=time.time()-began,new_env=0,new_model=0,new_train=0,new_physics=0),ensure_ascii=False))
if __name__=='__main__':main()
