"""Keep full fork-state checks while hashing long recorded traces incrementally."""
from freeze import *
def main():
 path=STUDY/'deps/fork_core.py';text=path.read_text()
 if 'STREAMING_FULL_STATE_FINGERPRINT_V1' in text:return
 root=STUDY/'source_history/fork_streaming_fingerprint_v1';root.mkdir(exist_ok=False);shutil.copy2(path,root/'fork_core_before.py');before=sha(path)
 needle="  if isinstance(x,(list,tuple)):return [walk(v,path+'.'+str(i)) for i,v in enumerate(x)]"
 replacement="""  # STREAMING_FULL_STATE_FINGERPRINT_V1: every logged row contributes,
  # without materializing a second copy of an entire physics trace.
  if isinstance(x,list) and len(x)>512 and ('trace' in path or 'reference_rows' in path):
   h=hashlib.sha256();encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False)
   for item in x:
    h.update(b'ROW\\0')
    for part in encoder.iterencode(clean(item)):h.update(part.encode())
   return dict(streaming_full_rows_sha256=h.hexdigest(),length=len(x),all_rows_included=True)
  if isinstance(x,(list,tuple)):return [walk(v,path+'.'+str(i)) for i,v in enumerate(x)]"""
 assert text.count(needle)==1;path.write_text(text.replace(needle,replacement));save(root/'PATCH_MANIFEST.json',dict(path=str(path),before_sha256=before,after_sha256=sha(path),scientific_changes=[],physical_state_fork_unchanged=True,all_recorded_trace_rows_hashed=True,no_subsampling=True))
 source=json.loads((STUDY/'SOURCE.json').read_text());source['frozen_files'][str(path)]=sha(path);save(STUDY/'SOURCE.json',source)
 print('STREAMING_FORK_FINGERPRINT_INSTALLED')
if __name__=='__main__':main()
