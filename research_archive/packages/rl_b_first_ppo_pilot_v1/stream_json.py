"""Bounded-memory reader for a named JSON array in saved pretty/compact evidence."""
import json,re,gzip
def read_evidence(path,**kwargs):
    p=Path(path)
    return open(p,**kwargs) if p.exists() else gzip.open(str(p)+".gz","rt",**kwargs)
from pathlib import Path

def object_value(path,key):
    pattern=re.compile(r'"'+re.escape(key)+r'"\s*:\s*');dec=json.JSONDecoder();buffer='';found=False
    with read_evidence(path,encoding='utf-8') as f:
        while True:
            chunk=f.read(65536)
            if not chunk:raise ValueError('missing or truncated JSON value: '+key)
            buffer+=chunk
            if not found:
                match=pattern.search(buffer)
                if match:buffer=buffer[match.end():];found=True
                else:buffer=buffer[-4096:];continue
            try:return dec.raw_decode(buffer.lstrip())[0]
            except json.JSONDecodeError:
                if len(buffer)>16*1024*1024:raise MemoryError('single value exceeds bounded parser budget')
def array_items(path,key):
    pattern=re.compile(r'"'+re.escape(key)+r'"\s*:\s*([\[{])')
    dec=json.JSONDecoder();buffer='';found=False
    with read_evidence(path,encoding='utf-8') as f:
        while not found:
            chunk=f.read(65536)
            if not chunk:raise KeyError('array not found: '+key)
            buffer+=chunk;match=pattern.search(buffer)
            if match:
                if match.group(1)=='{':
                    descriptor=object_value(path,key)
                    root=next(p for p in Path(path).resolve().parents if (p/'STUDY_CONFIG.json').exists())
                    target=(root/descriptor['external_jsonl_relative_to_study']).resolve()
                    if not target.is_relative_to(root):raise ValueError('EXTERNAL_EVIDENCE_OUTSIDE_STUDY')
                    count=0
                    with read_evidence(target,encoding='utf-8') as rows:
                        for line in rows:count+=1;yield json.loads(line)
                    if count!=descriptor['count']:raise ValueError('EXTERNAL_EVIDENCE_COUNT_MISMATCH')
                    return
                buffer=buffer[match.end():];found=True
            else:buffer=buffer[-4096:]
        while True:
            buffer=buffer.lstrip()
            if buffer.startswith(','):buffer=buffer[1:].lstrip()
            if buffer.startswith(']'):return
            try:item,end=dec.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk=f.read(65536)
                if not chunk:raise ValueError('truncated JSON array: '+key)
                buffer+=chunk
                if len(buffer)>16*1024*1024:raise MemoryError('single evidence row exceeds bounded parser budget')
                continue
            yield item;buffer=buffer[end:]
