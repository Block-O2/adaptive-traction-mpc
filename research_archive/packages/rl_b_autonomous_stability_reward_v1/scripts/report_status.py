"""Lightweight progress reports from immutable per-attempt summaries."""
import json,time,os,sys
from collections import defaultdict
from research_common import ROOT,RUNTIME,HARD_STOP,NO_TRAIN,STATE,atomic,read,resources,now,pid_identity
from datetime import datetime
T0=datetime.fromisoformat(STATE['t0_utc']).timestamp()

def snapshot(label=None):
    ledger=read(ROOT/'LEDGER.json',dict(training_attempts=0,evaluation_attempts=0,native_steps=0,optimizer_steps=0,rl_decisions=0,attempts=[]))
    rows=[]
    if (ROOT/'ALL_ATTEMPTS.jsonl').exists():
        for line in (ROOT/'ALL_ATTEMPTS.jsonl').read_text().splitlines():
            try:rows.append(json.loads(line))
            except json.JSONDecodeError:continue
    groups=defaultdict(lambda:dict(training=0,training_successes=0,evaluations=0,deterministic_successes=0,deterministic_attempts=0,stochastic_successes=0,stochastic_attempts=0))
    for x in rows:
        g=groups[x['branch']]
        if x['mode']=='training':g['training']+=1;g['training_successes']+=int(x['success'])
        else:
            g['evaluations']+=1;mode=x['policy_mode'];g[mode+'_attempts']+=1;g[mode+'_successes']+=int(x['success'])
    left=dict(training_attempts=450-ledger['training_attempts'],evaluation_attempts=60-ledger['evaluation_attempts'],
              native_steps=50000000-ledger['native_steps'],wall_seconds=max(0.,HARD_STOP-time.time()),
              new_training_seconds=max(0.,NO_TRAIN-time.time()))
    active=[read(p) for p in (ROOT/'owned').glob('*.json') if 'ended' not in read(p) and read(p).get('worker')]
    state=read(ROOT/'RESEARCH_STATE.json',{})
    phase=active[-1]['job'].split('_seed')[0] if active else state.get('phase')
    if state.get('status') not in ['STOP','NEEDS_AGENT_DIAGNOSIS','AWAITING_AGENT_RESEARCH_REVIEW']:
        for key in ['training_attempts','evaluation_attempts','native_steps','owned_processes']:state.pop(key,None)
        state.update(status='RUNNING',phase=phase,time_utc=now(),live_budget='LEDGER.json',live_progress='LIVE_STATUS.json')
        atomic(ROOT/'RESEARCH_STATE.json',state)
    result=dict(time_utc=now(),elapsed_h=(time.time()-T0)/3600,phase=phase,
        counts={k:v for k,v in ledger.items() if k!='attempts'},remaining=left,branches=dict(groups),
        resources=resources(),active_owned=active,
        G4_STRICT_PASS='FAIL',STAGE2_READY='NOT_READY',FINAL_CAMPAIGN_READY='NOT_READY')
    atomic(ROOT/'LIVE_STATUS.json',result)
    if label:
        text=f'# {label} 内部阶段报告\n\n生成UTC：{result["time_utc"]}；实际elapsed {result["elapsed_h"]:.3f}小时。此报告不是STOP信号。\n\n'
        text+=f'累计训练attempt {ledger["training_attempts"]}，冻结评价attempt {ledger["evaluation_attempts"]}，native steps {ledger["native_steps"]}，RL decisions {ledger["rl_decisions"]}，Adam steps {ledger["optimizer_steps"]}。未结算attempt仍保留硬预留。\n\n'
        text+='|分支|训练完成/attempt|确定性冻结完成|随机冻结完成|\n|---|---|---|---|\n'
        for branch,g in groups.items():text+=f'|{branch}|{g["training_successes"]}/{g["training"]}|{g["deterministic_successes"]}/{g["deterministic_attempts"]}|{g["stochastic_successes"]}/{g["stochastic_attempts"]}|\n'
        text+='\n以上跨checkpoint累计只描述已执行事实，不能当作单策略稳定完成率。当前候选和具体选择以STABILITY_SELECTION.json及RESEARCH_DECISION_LOG.jsonl为准。\n\n'
        text+=f'剩余硬预算：训练{left["training_attempts"]}、评价{left["evaluation_attempts"]}、native {left["native_steps"]}；距硬截止{left["wall_seconds"]/3600:.2f}小时。\n\n'
        text+='下一阶段：继续有限队列或按Agent反思分配跨seed保持、必要消融及未见动作流复核；到9h15m停止新训练。独立物理初态接口BLOCKED，G4_STRICT_PASS=FAIL，新live matched不完整，Stage2及正式Campaign均NOT_READY。普通任务失败只停止分支，不停止研究包。\n'
        (ROOT/f'{label}.md').write_text(text)
    return result

def main():
    atomic(ROOT/'STATUS_MONITOR_START.json',dict(time_utc=now(),identity=pid_identity(os.getpid())))
    while not (ROOT/'END.json').exists():
        elapsed=(time.time()-T0)/3600
        for hour in [2,4,6,8]:
            label=f'PHASE_{hour}H'
            if elapsed>=hour and not (ROOT/f'{label}.md').exists():snapshot(label)
        snapshot()
        if time.time()>=HARD_STOP-5:break
        time.sleep(15)
    atomic(ROOT/'STATUS_MONITOR_END.json',dict(time_utc=now(),pid=os.getpid()))
if __name__=='__main__':
    if '--once' in sys.argv:snapshot()
    else:main()
