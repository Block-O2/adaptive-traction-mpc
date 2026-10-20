import gzip,json
def array_items(path,key):
 with gzip.open(path,'rt') as f:
  buf='';needle='"'+key+'":';found=False;decoder=json.JSONDecoder()
  while not found:
   part=f.read(65536)
   if not part:return
   buf+=part;pos=buf.find(needle)
   if pos>=0:
    buf=buf[pos+len(needle):].lstrip()
    while not buf:buf+=f.read(65536);buf=buf.lstrip()
    if not buf.startswith('['):raise ValueError('NOT_ARRAY:'+key)
    buf=buf[1:];found=True
   else:buf=buf[-len(needle):]
  while True:
   buf=buf.lstrip(', \n\r\t')
   if buf.startswith(']'):return
   try:value,end=decoder.raw_decode(buf)
   except json.JSONDecodeError:
    part=f.read(65536)
    if not part:raise ValueError('INCOMPLETE_ARRAY:'+key)
    buf+=part
    if len(buf)>4*2**20:raise ValueError('ITEM_EXCEEDS_BOUNDED_EXTRACTION:'+key)
    continue
   yield value;buf=buf[end:]
