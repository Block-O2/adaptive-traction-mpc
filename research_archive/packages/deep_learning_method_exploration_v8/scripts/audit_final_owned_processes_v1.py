"""Read-only final process identity audit; never kills or guesses old start ticks."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import os
import time

P=Path(__file__).resolve().parents[1]
TOKENS=('START','END','EXECUTION','PROCESS','RESOURCE','OWNER','CLOSURE','BUILD')


def stat(pid):
    try:
        tail=Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
        return dict(pid=pid,start_ticks=int(tail[19]),state=tail[0],ppid=int(tail[1]))
    except (FileNotFoundError,ProcessLookupError):return None


def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',required=True);args=cli.parse_args()
    target=(P/args.output).resolve();assert target.is_relative_to(P) and not target.exists()
    known=collections.defaultdict(list);unrecorded=[];sources={};parse_errors=[]
    def visit(value,source,pointer):
        if isinstance(value,dict):
            pid=value.get('pid',value.get('PID'))
            if isinstance(pid,int) and not isinstance(pid,bool) and pid>0:
                ticks=value.get('start_ticks');e=dict(source=source,json_pointer=pointer,pid=pid)
                if isinstance(ticks,int) and not isinstance(ticks,bool) and ticks>0:
                    known[(pid,ticks)].append(e)
                else:unrecorded.append(e)
            for key,item in value.items():visit(item,source,pointer+'/'+str(key).replace('~','~0').replace('/','~1'))
        elif isinstance(value,list):
            for index,item in enumerate(value):visit(item,source,pointer+'/'+str(index))
    for folder in ['owned','audit','families','freeze']:
        for path in (P/folder).rglob('*.json'):
            if not any(token in path.name.upper() for token in TOKENS):continue
            if path.name.startswith('HISTORY_'):continue
            relative=str(path.relative_to(P))
            try:
                raw=path.read_bytes();value=json.loads(raw)
                sources[relative]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw));visit(value,relative,'')
            except (OSError,ValueError) as error:parse_errors.append(dict(path=relative,error=str(error)))
    identities=[];live=[]
    for (pid,ticks),evidence in sorted(known.items()):
        current=stat(pid);active=current is not None and current['start_ticks']==ticks
        row=dict(pid=pid,original_start_ticks=ticks,current=current,original_identity_alive=active,evidence=evidence)
        identities.append(row)
        if active:live.append(row)
    # The current audit and its tool ancestors are packaging machinery, enumerated
    # explicitly rather than silently counted as old scientific experiment owners.
    ancestors=[];cursor=os.getpid()
    while cursor>0:
        current=stat(cursor)
        if current is None:break
        ancestors.append(current);cursor=current['ppid']
    ancestor_ids={row['pid'] for row in ancestors};package_processes=[]
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) in ancestor_ids:continue
        try:cmdline=(entry/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
        if str(P) in cmdline or P.name in cmdline:
            package_processes.append(dict(identity=stat(int(entry.name)),command=cmdline))
    unknown=[{**row,'current':stat(row['pid']),'original_start_ticks':'UNKNOWN_NOT_RECONSTRUCTED'} for row in unrecorded]
    out=dict(schema='v8.final_owned_process_identity_audit.v1',created_unix=time.time(),
             status='NO_KNOWN_OR_PACKAGE_RESEARCH_PROCESS_LIVE' if not live and not package_processes and not parse_errors else 'EXPLICIT_LIVE_OR_METADATA_ERROR',
             identities=identities,known_unique_PID_starttick_count=len(identities),live_original_identities=live,
             package_related_processes_excluding_current_tool_ancestors=package_processes,
             unrecorded_starttick_metadata_not_fabricated=unknown,parse_errors=parse_errors,
             sources=sources,excluded_current_packaging_ancestors=ancestors,
             source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             new_model_scorer_raw_physics_calls=0,process_mutations=0,
             scope='Exact original PID/starttick checks plus current package-command scan; missing original ticks remain UNKNOWN. Current finite packaging tool ancestry listed separately.')
    with target.open('x') as stream:json.dump(out,stream,indent=2);stream.write('\n')
    print(json.dumps({k:out[k] for k in ['status','known_unique_PID_starttick_count','live_original_identities','package_related_processes_excluding_current_tool_ancestors','parse_errors']}))


if __name__=='__main__':main()
