"""Append one final v7 result entry after validating the historical prefix."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import time

P = Path(__file__).resolve().parents[1]
J = P.parent / 'RESEARCH_DECISION_JOURNAL.md'
dest = P / 'audit/JOURNAL_PREFIX_FINAL.json'
assert not dest.exists()
prefix = json.loads((P / 'audit/JOURNAL_PREFIX.json').read_text())
before = J.read_bytes()
assert hashlib.sha256(before[:prefix['bytes']]).hexdigest() == prefix['sha256'], 'ORIGINAL_JOURNAL_PREFIX_CHANGED'
tag = 'v7 最终结果与负结果（封包核验）'
assert tag.encode() not in before, 'DUPLICATE_FINAL_APPEND_REFUSED'
body = '本轮170次物理尝试全部闭合，新增12,997,720 native独立复算，历史全量哈希通过。传统组合两冻结前缀微双降，几何变体反转；重型早启H150改善平顺性但增加JM。GP与二次面同选且JM失败；两stump交叉状态benefit均零、不及常数B，未部署。八私有Adam仅为诊断，fresh PPO公平桥接未闭合。轻型路径与四合法时间因子全失格。失败、partial和存证缺口保留；下一步先查完整动作排序和RL接口，封包后STOP，无自动下一轮。'
assert 150 <= len(body) <= 300, len(body)
now = time.time()
text = '\n\n### ' + datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat() + ' — ' + tag + '\n\n' + body + '\n'
payload = text.encode()
with J.open('ab') as f:
    f.write(payload)
    f.flush()
    os.fsync(f.fileno())
after = J.read_bytes()
assert after == before + payload
result = {
    'status': 'PASS', 'created_unix': now,
    'process': {'pid': os.getpid(), 'start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])},
    'journal_path': str(J), 'original_prefix_bytes': prefix['bytes'], 'original_prefix_sha256': prefix['sha256'],
    'original_prefix_preserved': hashlib.sha256(after[:prefix['bytes']]).hexdigest() == prefix['sha256'],
    'before_bytes_preserved': after[:len(before)] == before,
    'before_bytes': len(before), 'before_sha256': hashlib.sha256(before).hexdigest(),
    'append_bytes': len(payload), 'append_sha256': hashlib.sha256(payload).hexdigest(),
    'after_bytes': len(after), 'after_sha256': hashlib.sha256(after).hexdigest(),
    'body_characters': len(body), 'duplicate_final_entry': False,
    'only_append_no_history_overwrite': True,
    'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
with dest.open('x') as f:
    f.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print('JOURNAL_FINAL_APPEND_PASS', len(body), 'characters', result['after_sha256'])
