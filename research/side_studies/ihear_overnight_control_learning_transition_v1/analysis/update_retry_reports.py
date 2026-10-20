"""Adapt final authoring/audits to preserve both original and repaired pilots."""
from pathlib import Path
import ast,textwrap
R=Path(__file__).resolve().parents[1]
f=R/'analysis/verify_science.py';s=f.read_text()
assert 'for feedback_group' not in s
s=s.replace('import numpy as np','import numpy as np\nfrom repetition_paths import rep_path,RepeatRoot')
a=s.index("if (P/'models/REPETITION_MEMORY_V1.json').exists():");b=s.index('complete=[]',a)
block=s[a:b].replace('P/','FR/').replace('read(','fr_read(')
block=block.replace("s['id']=='REP_parent'","s['id']==rep_path('REP_parent',feedback_group)")
block=block.replace("checks['actual_previous_feedback_recomputed']","checks['actual_previous_feedback_recomputed_'+feedback_group]")
block=block.replace('        from feedback_selector import select as feedback_select',"        import importlib\n        feedback_select=importlib.import_module('feedback_selector_retry' if feedback_group=='REPR' else 'feedback_selector').select")
s=s[:a]+"for feedback_group in ['REP','REPR']:\n    FR=RepeatRoot(feedback_group)\n    def fr_read(n):return read(rep_path(n,feedback_group))\n"+textwrap.indent(block,'    ')+s[b:]
old="read('output/REPETITION_CONTINUITY_BEFORE_SECOND.json')['second_initial']['physical_time_s'] if folder.name=='REP_parent'"
new="read(rep_path('output/REPETITION_CONTINUITY_BEFORE_SECOND.json',folder.name.split('_')[0]))['second_initial']['physical_time_s'] if folder.name in ['REP_parent','REPR_parent']"
assert old in s;s=s.replace(old,new)
ast.parse(s);f.write_text(s)
f=R/'analysis/write_final_reports.py';s=f.read_text()
s=s.replace('import json,time,datetime,collections','import json,time,datetime,collections\nfrom repetition_paths import rep_path')
s=s.replace("r['parent']!='REP'","r['parent'] not in ['REP','REPR']")
s=s.replace("def flag(x):", "def append_final(n,section):\n    title=section.strip().splitlines()[0];base=(P/n).read_text().split('\\n'+title,1)[0]\n    doc(n,base.rstrip()+'\\n\\n'+section.strip())\ndef flag(x):")
for n in ['LEARNING_DATASET_AUDIT.md','RL_BASELINE_STUDY.md']:
    old="with (P/'"+n+"').open('a') as f:f.write("
    assert old in s;s=s.replace(old,"append_final('"+n+"',")
anchor="doc('FEW_REPETITION_EVALUATION.md',f'''"
s=s.replace(anchor,"if rep.get('run_prefix')=='REPR':reptext+=' 首次REP在第二次调用的序列化所有权检查中失败，未推进第二次physics；另保留一次零物理启动日志命名失败。随后以新代码身份修复并完整重跑，原失败、权重与门槛均保留。详见REPETITION_SERIALIZER_REPAIR.md。'\n"+anchor)
for name in ['audit/REPETITION_FIRST_REPRODUCTION.json','output/REPETITION_CONTINUITY_BEFORE_SECOND.json','output/REP_BOUNDARY_NATIVE.json','models/REPETITION_MEMORY_FREEZE.json']:
    s=s.replace(name,"{rep_path('"+name+"')}")
s=s.replace('执行manifest v2/v3/v4','执行manifest v2/v3/v4及序列化修复v5/v6')
s=s.replace('v4增加真实持续重复及反馈选择；','v4增加真实持续重复及反馈选择，v5/v6仅修复序列化恢复和独立启动日志；')
s=s.replace('首次D01导入失败发生在物理之前，','重复pilot的初次序列化错误及v5启动日志错误完整保留，第二次任务未推进的0 native成本由连续时钟证明；v5启动失败时间为事后登记时间，未伪造精确墙钟耗时。首次D01导入失败发生在物理之前，')
ast.parse(s);f.write_text(s)
print('RETRY_REPORT_AUTHORING_UPDATED',flush=True)
