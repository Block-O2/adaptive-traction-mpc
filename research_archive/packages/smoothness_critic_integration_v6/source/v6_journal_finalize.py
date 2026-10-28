"""Append-only final root journal entry, with original and snapshot prefix hashes."""
from pathlib import Path
import json,time,datetime,hashlib
P=Path(__file__).resolve().parents[1];J=P.parent/'RESEARCH_DECISION_JOURNAL.md'
def read(n):return json.loads((P/n).read_text())
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    old=read('audit/JOURNAL_BEFORE.json');b=J.read_bytes()
    assert sha(b[:old['bytes']])==old['sha256'],'OLD_JOURNAL_PREFIX_MODIFIED'
    assert read('audit/OWNED_PROCESS_FINAL.json')['status']=='PASS','OWNED_CLEANUP_REQUIRED'
    a=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json');e=read('analysis/COMBINED_FROZEN_RESULTS.json');s=read('analysis/PROSPECTIVE_SAMPLE_EFFICIENCY.json');r=read('analysis/ADAPTIVE_FIXED_RULE_RESULTS.json')
    assert a['physical_START']==a['physical_END'] and e['primary_states']==4,'RESEARCH_NOT_COMPLETE'
    act=read('ACTIVATION.json');heading='— v6 结束 ['+act['activation_id']+']';text=b.decode();phase=read('analysis/FIXED_PHASE_RULE_RESULTS.json')
    phase_text='固定阶段组合在两组配对中通过原门并同时降低JF/JM。' if len(phase['rows'])==2 and all(r['predeclared_extra_quality_and_cost_bounds_pass'] for r in phase['rows']) else '固定阶段方案实际结果与取舍保留在本轮报告。'
    body=(f"已知v5平顺性收益已由原raw和匹配完整执行复核。本轮实际完成{a['physical_START']}次MuJoCo尝试，"
          f"{a['actual_new_native_steps']}个新增native步；主Critic在{e['primary_states']}个冻结新prefix中{e['critic_qualified_states']}个通过原门，"
          f"超越1秒与强固定阶段规则的独立收益状态为{len(e['meaningful_independent_increment_states'])}。"
          f"修正了缩放、因果历史和后续标签，保留旧上游不匹配的完整失败；风险模型仍漏检，不能替代原门。"
          f"传统事前筛选实际省略{s['prospectively_omitted_unique_complete_candidate_runs']}个唯一候选续跑，尚无整体摊销净节省证明。"
          +phase_text+"最后配置微扰实际为训练父状态重放，已剔除独立证据。未完成精确在线native资格、独立出程修复与患者泛化。下一步先核验真实新状态及强规则外排序变化，再决定学习投入。owned已归零，本轮STOP。")
    if heading not in text:
        stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        entry='\n\n## '+stamp+' UTC '+heading+'\n\n'+body+'\n'
        with J.open('ab') as f:f.write(entry.encode())
        (P/'audit/JOURNAL_END_ENTRY.txt').write_text(entry)
    else:assert text.count(heading)==1,'DUPLICATE_V6_END_ENTRY'
    after=J.read_bytes();out=dict(status='PASS' if after[:old['bytes']]==b[:old['bytes']] else 'FAIL',
        original_bytes=old['bytes'],original_sha256=old['sha256'],snapshot_bytes=len(after),
        snapshot_sha256=sha(after),recorded_unix=time.time(),v5_original_entries_preserved=old['v5_entries'],
        v6_end_entries=after.decode().count(heading),append_only=True,
        note='Future journal appends permitted; the sealed prefix through snapshot_bytes must remain byte-identical.')
    (P/'audit/JOURNAL_APPEND_ONLY_FINAL.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print('JOURNAL_FINAL',out['status'],'end_entries',out['v6_end_entries'],flush=True)
if __name__=='__main__':main()
