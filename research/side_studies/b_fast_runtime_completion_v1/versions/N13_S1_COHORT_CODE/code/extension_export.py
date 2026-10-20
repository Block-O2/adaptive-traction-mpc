from extension_common import *

def data():
    def size(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    wsl=size(STUDY);windows=size(FIRST_DELIVERY.parent)
    save(EXT/'DATA_ACCOUNTING.json',dict(unix=time.time(),WSL_logical_bytes=wsl,Windows_logical_bytes=windows,total_bytes=wsl+windows,status='PASS' if wsl+windows<10*2**30 else 'FAIL',scope='Both full new-study directories and all duplicate/history files; point-time logical bytes, not allocated blocks. This measurement precedes final supplement export; later manifest records copy increment.'))
    assert wsl+windows<10*2**30

def inputs():
    timer=json.loads((EXT/'TIMER_SERVICE.json').read_text());paths={r['snapshot']:r['snapshot_sha256'] for r in timer['rows']}
    root=EXT/'inputs'
    for name,digest in paths.items():
        p=Path(name);assert sha(p)==digest;dest=root/'saved_states'/p.parent.name/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    id='325_NOON_B_ACTIVATION_CAPTURE';folder=root/'actual_failure';folder.mkdir(parents=True,exist_ok=True)
    for p in (STUDY/'source/results'/id).iterdir():
        if p.is_file():shutil.copy2(p,folder/p.name)
    for suffix in ('_RESULT.json','_PARTIAL_COMPUTE.json','_TIMING_PROFILE.json'):
        p=STUDY/'output'/(id+suffix)
        if p.exists():shutil.copy2(p,folder/p.name)
    save(EXT/'INPUT_MANIFEST.json',dict(saved_state_files=len(paths),actual_failed_epoch=id,all_saved_state_bytes_match_original=True,raw_inputs_retained=True,physics_replayed=False))

def export():
    target=WIN_EXT/'delivery';target.mkdir(exist_ok=True);entries=[]
    for p in sorted(EXT.rglob('*')):
        if not p.is_file() or p.name.endswith(('.lock','.tmp')) or p.name in ('DELIVERY_MANIFEST.json','DELIVERY_VALIDATION.json'):continue
        rel=p.relative_to(EXT);d=target/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,d);assert sha(p)==sha(d)
        entries.append(dict(path=str(rel),sha256=sha(d),bytes=d.stat().st_size))
    manifest=dict(status='BYTE_VERIFIED_EXPORT',unix=time.time(),entries=entries,files=len(entries),bytes=sum(r['bytes'] for r in entries),original_delivery_untouched=True)
    save(target/'DELIVERY_MANIFEST.json',manifest);print(json.dumps({k:manifest[k] for k in ('status','files','bytes')}))

if __name__=='__main__':
    {'inputs':inputs,'data':data,'export':export}[sys.argv[1]]()
