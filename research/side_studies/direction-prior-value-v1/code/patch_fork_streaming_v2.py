from freeze import *
def main():
 path=STUDY/'deps/fork_core.py';text=path.read_text()
 if 'STREAMING_FULL_STATE_FINGERPRINT_V2' in text:return
 root=STUDY/'source_history/fork_streaming_fingerprint_v2';root.mkdir(exist_ok=False);shutil.copy2(path,root/'fork_core_before.py');before=sha(path)
 text=text.replace('import threading,random,types,mujoco,pickle,traceback','import threading,random,types,mujoco,pickle,traceback,collections')
 needle="  if isinstance(x,Path):return str(x)"
 replacement="""  if isinstance(x,(bytes,bytearray,memoryview)):return dict(bytes_sha256=hashlib.sha256(x).hexdigest(),length=len(x))
  if isinstance(x,np.random.Generator):return dict(generator_state=clean(x.bit_generator.state),generator_type=type(x.bit_generator).__name__)
  if isinstance(x,collections.deque):return [walk(v,path+'.deque.'+str(i)) for i,v in enumerate(x)]
  if isinstance(x,Path):return str(x)"""
 assert text.count(needle)==1;text=text.replace(needle,replacement)
 start=text.index('  # STREAMING_FULL_STATE_FINGERPRINT_V1');end=text.index("  if isinstance(x,(list,tuple)):",start)
 text=text[:start]+"""  # STREAMING_FULL_STATE_FINGERPRINT_V2: every long list, including sensor
  # histories, is checked row-by-row without expanding a second full trace.
  if isinstance(x,list) and len(x)>512:
   h=hashlib.sha256();encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False)
   for i,item in enumerate(x):
    row=hashlib.sha256()
    try:
     for part in encoder.iterencode(clean(item)):row.update(part.encode())
    except (TypeError,ValueError):
     row=hashlib.sha256()
     for part in encoder.iterencode(walk(item,path+'.'+str(i))):row.update(part.encode())
    h.update(b'ROW\\0');h.update(row.digest())
   return dict(streaming_full_rows_sha256=h.hexdigest(),length=len(x),all_rows_included=True)
"""+text[end:]
 path.write_text(text);save(root/'PATCH_MANIFEST.json',dict(before_sha256=before,after_sha256=sha(path),all_long_histories_streamed=True,measurement_generator_RNG_state_explicit=True,deque_and_native_cache_bytes_explicit=True,physics_changes=[],reason='v1 still expanded sensor histories into157MB snapshot; memory trimming removed after a hash mismatch; v2 never omits or downsamples rows'))
 source=json.loads((STUDY/'SOURCE.json').read_text());source['frozen_files'][str(path)]=sha(path);save(STUDY/'SOURCE.json',source);print('FORK_STREAMING_V2_INSTALLED')
if __name__=='__main__':main()
