"""Review links to original frozen source, copied by export_delivery."""
from task_bootstrap import *
WIN='C:/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/delivery'
def main():
 index=json.loads((STUDY/'reports/SOURCE_EVIDENCE_INDEX.json').read_text());names=[Path(r['path']).name for r in index['rows']];assert len(names)==len(set(names))
 text=['# 原生时钟和执行链源码索引','', '这些文件是冻结副本的审阅导出。源码哈希、完整上下文与原WSL路径见 SOURCE_EVIDENCE_INDEX.json；下列链接使用实际Windows文件和原始行号。','', '40ms是物理bridge时长；严格<55ms是独立evaluator资格年龄；100ms是原lifecycle generic expiry。E5另用19ms proposal-return guard和36ms下游预留，不能当成第四个原生规则。','', '原source_capture_ns由physical sensor sample time映射到固定wall epoch；host_materialized_ns另记录真实host读取完成时刻。request_ns是原生可修改请求实际创建时刻。request-availability→activation与原生source-age分别列账，不能重打source stamp来缩短年龄。','', '单owner catch-up保留已写入的旧命令直到原prepare_apply目标；真实write晚于该fixed grid时，新命令step可作用于较早的名义wall-grid区间，尽管计算发生在真实write之后。该模拟滞后明确作为负面实时证据，不能宣称硬件及时部署。','', '当前模型重验必须用当前belief/reference/geometry；只能在完全相同immutable schedule及geometry signature时复用原几何certificate。mechanics、future handoff与rolling prefix都保留。','']
 for row in index['rows']:
  name=Path(row['path']).name;text.extend([f'## {name}','',f'SHA-256: `{row["sha256"]}`',''])
  for match in row['matches']:
   line=match['line'];literal=match['matched'].strip().replace('`',"'");text.append(f'- [{name}:{line}](<{WIN}/source/{name}:{line}>): `{literal}`')
  text.append('')
 text.extend(['## 原100ms比较符与原fixed-ready顺序','', 'PlanLifecycle.expired保留age>=100ms；WallPhysicsSession.apply写前/写后保留>100ms。严格evaluator始终要求<55ms，三种规则没有统一。','', '原runtime先做current-model/phase/splice/reference检查，然后prepare_apply积分旧command到固定ready目标，再做effective reference-motion复核及原expiry/actual write。prepare后的reference检查不是又一次完整model certificate。原命令、source stamp、epoch与已积分state均未重写。',''])
 text.extend(['## 冻结候选池与Q状态依赖','', 'native_core.candidates的c参数没有被使用；候选池直接由carry、attempted-count mask、seed及固定historical design生成。phase选择当前实际动作槽，当前state参与原生certificate与realization，并可通过历史间接影响carry/count。linear Q没有state×plan交互；同一候选/carry/count的状态变化是共同bias。具体AST和330次有限pool检查见Q_POOL_DEPENDENCY_AUDIT.json。',''])
 p=STUDY/'delivery/SOURCE_GUIDE.md';p.write_text('\n'.join(text)+'\n');save(STUDY/'reports/SOURCE_GUIDE_BUILD.json',dict(status='SOURCE_LINE_LINKS_GENERATED',source_index_sha256=sha(STUDY/'reports/SOURCE_EVIDENCE_INDEX.json'),files=len(names),links=sum(len(r['matches']) for r in index['rows']),guide_sha256=sha(p)))
 print(json.dumps(dict(files=len(names),links=sum(len(r['matches']) for r in index['rows']))))
if __name__=='__main__':main()
