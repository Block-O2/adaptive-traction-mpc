from extension_common import *

def main():
    result=dict(unix=time.time(),remaining_minutes=(DEADLINE-time.time())/60)
    for name in ('ACTIVE.json','RUN_PLAN.json','RESOURCE_STOP.json'):
        p=EXT/name
        if p.exists():
            x=json.loads(p.read_text());result[name]={k:x[k] for k in ('status','id','owner_pid','child_pid','deadline_unix','reason') if k in x}
    for p in sorted(EXT.glob('*_WORKER.log')):
        tail=p.read_text(errors='replace').splitlines()[-3:];brief=[]
        for line in tail:
            try:
                x=json.loads(line);brief.append({k:x[k] for k in ('status','id','error','wall_seconds','states','session','condition','completed_rows','cumulative_attempts','physics_attempts_added') if k in x})
            except ValueError:brief.append(line[:300])
        result[p.name]=brief
    p=EXT/'RESOURCE_LOG.jsonl'
    if p.exists():
        x=json.loads(p.read_text().splitlines()[-1]);result['last_resource']={k:x[k] for k in ('unix','mem_available','swap_used','swap_in','swap_out','oom_kill','PSS','owned_count','windows')}
    print(json.dumps(result))

if __name__=='__main__':main()
