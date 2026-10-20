from explore_common import *
import shutil,collections
def main():
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 win=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/m2_coordination_space_exploration_v1')
 assert load(S/'PACKAGE_VERIFICATION.json')['status']=='PASS';assert load(win/'DELIVERY_VERIFICATION.json')['status']=='PASS'
 data=load(S/'SEARCH_RESULTS.json');fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
 for c in data['comparisons']:
  color='#147d64' if c['acceptance_pass'] else '#b74343';label=c['candidate'].split('_')[0]
  for ax,key in zip(axes,['velocity_deg_s/p95_abs','acceleration_deg_s2/p95_abs']):
   ax.scatter(c['gain_percent'],c['burden_ratios'][key][1],color=color,s=48)
   if c['acceptance_pass'] or label=='002':ax.annotate(label,(c['gain_percent'],c['burden_ratios'][key][1]),xytext=(5,8),textcoords='offset points',fontsize=9)
 for ax,title in zip(axes,['Knee p95 speed / B','Knee p95 acceleration / B']):
  ax.axhline(1,color='#777777',ls=':');ax.axhline(1.1,color='#d39823',ls='--');ax.set(xlabel='Full-task J_F reduction versus B (%)',ylabel=title,title=title);ax.grid(alpha=.18)
 fig.suptitle('Discovery only: green = primary gates pass; red = excluded\nLabels identify eligible tables and frozen M2; selected table failed held-seed validation',fontsize=11)
 fig.savefig(S/'COORDINATION_TRADEOFF.png',dpi=160);fig.savefig(S/'COORDINATION_TRADEOFF.svg');plt.close(fig)
 report=(S/'REPORT.md').read_text();point='实际新增物理attempt'
 pos=report.index(point)
 summary='搜索中 **3/12** 表候选通过主比较条件；选定0.10倍RETURN表，发现阶段J_F下降 **4.1077%**。两个保留seed的J_F收益分别 **+0.1491%** 与 **−2.3865%**（负值表示变差），主接受条件 **0/2 PASS**。两组均未通过加速度条件，第一组另未通过jerk；不得宣称VALIDATED或优于旧M2。Stage D新增物理运行0。\n\n'
 report=report[:pos]+summary+report[pos:]
 axes=[load(p) for p in (S/'reports').glob('*_AXES.json')];counts={k:dict(collections.Counter(r[k] for r in axes)) for k in ['PHYSICAL_TASK_VALID','HOST_EXECUTION_CAUSAL_VALID','LEGACY_R2_MATCHED','LEGACY_STRICT55']}
 report+='\n本轮独立资格轴分母22：'+json.dumps(counts,ensure_ascii=False)+'。R2/strict55结果不是研究motion接受条件，也不是正式实时资格。\n\n图表标签经可读性修订，只标记合格发现候选及M2；完整13个非B点及所有排除原因保留在SEARCH_RESULTS。final_polish.py仅更新展示、机械导出清单和资格轴摘要，不修改科学结果、阈值、选择或原始数据。\n'
 (S/'REPORT.md').write_text(report)
 for name in ['close_explore.py','final_polish.py']:shutil.copy2(win/name,S/'code'/name)
 closure=load(S/'PACKAGE_CLOSED.json');closure['final_display_export_unix']=time.time();closure['final_display_elapsed_s']=time.time()-load(S/'EXPERIMENT_PROTOCOL.json')['start_unix'];save(S/'PACKAGE_CLOSED.json',closure)
 verification=load(S/'PACKAGE_VERIFICATION.json');verification['final_display_polish']=dict(changes=['plot labels','report numerical synopsis','qualification axis summary'],scientific_changes=False);save(S/'PACKAGE_VERIFICATION.json',verification)
 changed=['REPORT.md','COORDINATION_TRADEOFF.png','COORDINATION_TRADEOFF.svg','PACKAGE_CLOSED.json','PACKAGE_VERIFICATION.json','code/close_explore.py','code/final_polish.py']
 for name in changed:shutil.copy2(S/name,win/name)
 manifest=load(S/'FULL_PACKAGE_MANIFEST.json')
 for name in changed:manifest['files'][name]=dict(bytes=(S/name).stat().st_size,sha256=sha(S/name))
 save(S/'FULL_PACKAGE_MANIFEST.json',manifest);shutil.copy2(S/'FULL_PACKAGE_MANIFEST.json',win/'FULL_PACKAGE_MANIFEST.json')
 mismatches=[name for name,info in manifest['files'].items() if not (win/name).is_file() or sha(win/name)!=info['sha256']]
 save(win/'DELIVERY_VERIFICATION.json',dict(status='PASS' if not mismatches else 'FAIL',copied_files=len(manifest['files']),mismatches=mismatches,canonical=str(S),display_polish=True))
 print(json.dumps(dict(status='PASS' if not mismatches else 'FAIL',mismatches=mismatches,axes=counts,elapsed_s=closure['final_display_elapsed_s'])),flush=True)
if __name__=='__main__':main()
