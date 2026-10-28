"""Final append-only journal, read-only Git and released physics-lock audit."""
from pathlib import Path
import json,time,datetime,hashlib,subprocess,os,fcntl
P=Path('/home/hank/ihear-lab/smoothness_critic_research_v5')
def read(n):return json.loads((P/n).read_text())
def put(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(x):return hashlib.sha256(x).hexdigest()
A=read('ACTIVATION.json');L=read('RESOURCE_AND_ATTEMPT_ACCOUNTING.json');pid=read('audit/OWNED_PID_FINAL_AUDIT.json');assert pid['status']=='PASS' and L['physical_START']==L['physical_END'] and read('audit/UNCHANGED_SCORER_REPLAY.json')['audited']==L['physical_START']
assert read('owned/FINAL_AUDIT_QUEUE_END.json')['reason']=='FINITE_POST_PHYSICS_AUDITS_COMPLETED'
g=read('audit/GIT_BEFORE.json');env=os.environ.copy();env['GIT_OPTIONAL_LOCKS']='0'
head=subprocess.check_output(['git','-C',g['repo'],'rev-parse','HEAD'],env=env,text=True).strip();status=subprocess.check_output(['git','-C',g['repo'],'status','--porcelain'],env=env,text=True)
git=dict(status='PASS' if head==g['HEAD'] and status==g['status'] else 'FAIL',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),repo=g['repo'],HEAD_before=g['HEAD'],HEAD_after=head,status_before=g['status'],status_after=status,commands=['git rev-parse HEAD','GIT_OPTIONAL_LOCKS=0 git status --porcelain'],no_git_mutation_authorized_or_performed=True)
put('audit/GIT_FINAL_AUDIT.json',git);assert git['status']=='PASS','GIT_IDENTITY_CHANGED'
with (P/'PHYSICS.lock').open('r') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_UN)
put('audit/PHYSICS_LOCK_FINAL.json',dict(status='PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exclusive_physics_lock_available=True,active_owned_processes=0,new_physical_START=0))
journal=P.parent/'RESEARCH_DECISION_JOURNAL.md';original=read('audit/JOURNAL_BEFORE.json');old=journal.read_bytes();assert sha(old[:original['size']])==original['sha256'],'ORIGINAL_JOURNAL_PREFIX_CHANGED'
key='Smoothness-Aware Control & Long-Horizon Critic v5 结束 ['+A['id']+']';start_key='Smoothness-Aware Control & Long-Horizon Critic v5 开始 ['+A['id']+']';oldtext=old.decode();assert oldtext.count(start_key)==1
body=f"本轮封包前实际约{(time.time()-A['t0_unix'])/3600:.2f}小时，完成{L['physical_START']}次MuJoCo物理执行并计账，保留全部失败。交接降速、pattern与相位组合在四个冻结prefix均通过原门；组合相对强固定降低实际jerk和施力波动，JF小升、JM下降。真实B策略续跑确认局部短视；Critic回程选对，但固定动作和1秒窗口相同，去程仍失败，常量字段诊断也未改变选择，真实尝试节省为零。分支模型独立信息收益未建立，PPO仅作冻结与显式接口修复。原guard、阈值及历史未改；原scorer、raw、source、日志和owned退出已核验，详细边界见独立研究包。最终封包STOP，无自动下一轮。"
assert 150<=len(body)<=300,len(body)
appended=False
if key not in oldtext:
 entry='\n\n---\n\n## '+datetime.datetime.now(datetime.timezone.utc).isoformat()+' UTC — '+key+'\n\n'+body+'\n'
 with journal.open('ab') as f:
  fcntl.flock(f,fcntl.LOCK_EX);f.write(entry.encode());f.flush();os.fsync(f.fileno());fcntl.flock(f,fcntl.LOCK_UN)
 appended=True
new=journal.read_bytes();text=new.decode();valid=sha(new[:original['size']])==original['sha256'] and new[:len(old)]==old and text.count(start_key)==1 and text.count(key)==1
result=dict(status='PASS' if valid else 'FAIL',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),journal=str(journal),activation_id=A['id'],original_bytes=original['size'],original_prefix_sha256=original['sha256'],original_history_prefix_preserved=sha(new[:original['size']])==original['sha256'],pre_append_prefix_preserved=new[:len(old)]==old,start_identity_occurrences=text.count(start_key),end_identity_occurrences=text.count(key),v4_workflow_review_occurrences=text.count('Constraint Geometry & Learning v4 流程回顾'),final_entry_body_characters=len(body),appended_this_call=appended,current_journal_bytes=len(new),current_journal_sha256=sha(new),scope='Historical bytes preserved, v4 missing workflow issue supplemented once, one v5 start/end. Final entry describes pre-seal elapsed time; exact completion time is END.json.')
put('audit/JOURNAL_FINAL_AUDIT.json',result);print('FINAL_JOURNAL',result['status'],'body_chars',len(body),'Git',git['status'],'lock_available',True);assert valid
