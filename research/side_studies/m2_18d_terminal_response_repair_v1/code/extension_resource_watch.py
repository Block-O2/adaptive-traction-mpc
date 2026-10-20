"""Resource-only sampling during report work; no dispatch or task revival."""
from extension_common import *
import os

def main():
    import runner
    save(EXT/'RESOURCE_WATCH_READY.json',dict(pid=os.getpid(),cmd=Path('/proc/self/cmdline').read_bytes().replace(b'\0',b' ').decode(),start_ticks=Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19],unix=time.time(),deadline_unix=DEADLINE))
    samples=0
    while time.time()<DEADLINE and not (EXT/'STOP_EXTENSION_RESOURCE').exists():
        active=EXT/'ACTIVE.json';state=json.loads(active.read_text()) if active.exists() else {}
        if state.get('status')=='IDLE':
            row=runner.sample(owner='NOON_EXTENSION_REPORT_SAMPLER_ONLY',filename='NOON_EXTENSION_RESOURCE_LOG.jsonl')
            row['scope']='Sampler only; active bounded jobs sample their own descendants separately.';append('RESOURCE_LOG.jsonl',row);samples+=1
        time.sleep(45)
    save(EXT/'RESOURCE_WATCH_STOP.json',dict(pid=os.getpid(),unix=time.time(),samples=samples,physics_dispatch=False,stopped=True))
    print(json.dumps(dict(status='RESOURCE_WATCH_STOPPED',samples=samples)))

if __name__=='__main__':main()
