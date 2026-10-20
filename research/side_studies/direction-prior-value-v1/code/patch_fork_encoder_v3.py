from freeze import *
import gc,tracemalloc,sys
def main():
 path=STUDY/'deps/fork_core.py';text=path.read_text();assert 'STREAMING_FULL_STATE_FINGERPRINT_V2' in text
 if 'BOUNDED_C_ROW_ENCODER_V3' in text:return
 root=STUDY/'source_history/fork_encoder_v3';root.mkdir(exist_ok=False);shutil.copy2(path,root/'fork_core_before.py')
 # encode() uses JSON's C one-shot encoder for each bounded row; iterencode()
 # constructs recursive Python closures afresh for every row and leaks those
 # into cyclic GC generations. Never encode the complete history as one row.
 old="for part in encoder.iterencode(clean(item)):row.update(part.encode())";new="row.update(encoder.encode(clean(item)).encode()) # BOUNDED_C_ROW_ENCODER_V3"
 assert text.count(old)==1;text=text.replace(old,new)
 old="for part in encoder.iterencode(walk(item,path+'.'+str(i))):row.update(part.encode())";new="row.update(encoder.encode(walk(item,path+'.'+str(i))).encode())"
 assert text.count(old)==1;text=text.replace(old,new)
 encoder=json.JSONEncoder(sort_keys=True,separators=(',',':'),allow_nan=False);examples=[]
 for i in range(1000):examples.append(dict(t=i*.00025,measurement=[i/13.,-i/17.,None],labels={'a':True,'x':'测量'},tuple_like=[[1,2,3]],state={'dtype':'float64','shape':[2],'sha256':hashlib.sha256(str(i).encode()).hexdigest()}))
 for row in examples:
  old_bytes=''.join(encoder.iterencode(row)).encode();new_bytes=encoder.encode(row).encode();assert old_bytes==new_bytes
 path.write_text(text)
 save(root/'PATCH_MANIFEST.json',dict(unix=time.time(),before_sha256=sha(root/'fork_core_before.py'),after_sha256=sha(path),schema_rows_byte_identical=1000,all_rows_retained=True,hash_format_unchanged=True,root_cause='Per-row recursive Python JSON iterencode closures retained millions of unreachable objects until cyclic collection; C one-shot encoding is bounded to one row',physics_changes=[]))
 source=json.loads((STUDY/'SOURCE.json').read_text());source['frozen_files'][str(path)]=sha(path);save(STUDY/'SOURCE.json',source);print('ENCODER_V3_BYTE_EQUIVALENCE_PASS')
if __name__=='__main__':main()
