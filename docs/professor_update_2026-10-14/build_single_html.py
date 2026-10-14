"""Bundle the current professor report into one self-contained offline HTML."""
from pathlib import Path
import base64,hashlib,html,json,mimetypes,re,shutil
from html.parser import HTMLParser
R=Path('/home/hank/coding/adaptive-traction-mpc-learning');D=R/'docs/professor_update_2026-10-14';W=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/docs/professor_update_2026-10-14')
source=(D/'index.html').read_text(encoding='utf-8');assert (W/'index.html').read_text(encoding='utf-8')==source
embedded_media={};embedded_documents={}
def resolve(ref):
 p=(D/ref).resolve()
 assert p.is_relative_to(D.resolve()),('outside package',ref)
 assert p.is_file(),('missing source',ref)
 return p
def embed_media(m):
 attr,quote,ref=m.groups()
 if ref.startswith(('data:','#')):return m.group(0)
 p=resolve(ref);raw=p.read_bytes();mime={'.mp4':'video/mp4','.png':'image/png'}.get(p.suffix.lower(),mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
 url='data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')
 embedded_media[ref]={'mime':mime,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
 return attr+'='+quote+url+quote
out=re.sub(r'\b(src|poster)=([\"\x27])([^\"\x27]+)\2',embed_media,source)
def embed_link(m):
 quote,ref=m.groups()
 if ref.startswith('#'):return m.group(0)
 p=resolve(ref);identifier='embedded-source-'+hashlib.sha256(ref.encode()).hexdigest()[:12]
 raw=p.read_bytes();embedded_documents[ref]={'id':identifier,'text':raw.decode('utf-8'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
 return 'href='+quote+'#'+identifier+quote
out=re.sub(r'\bhref=([\"\x27])([^\"\x27]+)\1',embed_link,out)
out=out.replace('<video ','<video playsinline webkit-playsinline ',3)
out=out.replace('所有资源均相对路径，可离线打开。','本文件已内嵌全部视频、图片与引用材料；离线打开即可展示。')
out=out.replace('<title>iHEAR Lab · Stage 5 Professor Update</title>','<title>iHEAR Lab · Professor Update · Single-file Offline Edition</title>')
details=''.join('<details class="embedded-source" id="'+e['id']+'"><summary>'+html.escape(ref)+'</summary><pre>'+html.escape(e['text'])+'</pre></details>' for ref,e in embedded_documents.items())
source_section='<section id="embedded-sources"><div class="number">EMBEDDED EVIDENCE / OFFLINE SOURCES</div><h2>内嵌来源材料</h2><p class="sub">正文的来源链接跳转到以下原文快照，无需其他文件。来源文字中的历史路径保留为研究出处。</p>'+details+'</section>'
out=out.replace('</main>',source_section+'\n</main>')
css='.embedded-source{margin:12px 0;border:1px solid var(--line);border-radius:8px;background:#fff}.embedded-source summary{cursor:pointer;padding:14px 18px;color:var(--teal);font-size:14px;overflow-wrap:anywhere}.embedded-source pre{margin:0;padding:18px;border-top:1px solid var(--line);max-height:65vh;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.65 "Segoe UI","Microsoft YaHei",sans-serif}'
out=out.replace('</style>',css+'\n</style>',1)
js='''<script>
function revealEmbeddedSource(){const id=location.hash.slice(1);if(!id.startsWith('embedded-source-'))return;const section=document.getElementById(id);if(section&&section.tagName==='DETAILS'){section.open=true;section.scrollIntoView({block:'start'});}}
window.addEventListener('hashchange',revealEmbeddedSource);window.addEventListener('DOMContentLoaded',revealEmbeddedSource);
</script>'''
out=out.replace('</body>',js+'\n</body>')
name='iHEAR_Professor_Update_2026-10-14.html';target=D/name;target.write_text(out,encoding='utf-8')
class Check(HTMLParser):
 def __init__(self):super().__init__();self.attrs=[];self.ids=[];self.sources=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.append(a['id'])
  for k in ['src','href','poster']:
   if k in a:self.attrs.append((tag,k,a[k]))
  if tag=='source':self.sources.append(a)
c=Check();c.feed(out);assert len(c.ids)==len(set(c.ids))
for tag,key,ref in c.attrs:
 if ref.startswith('#'):assert ref[1:] in c.ids,ref
 else:
  assert key in ['src','poster'] and ref.startswith('data:'),('external dependency',tag,key,ref[:100])
  header,payload=ref.split(',',1);raw=base64.b64decode(payload,validate=True)
  digest=hashlib.sha256(raw).hexdigest();assert digest in {v['sha256'] for v in embedded_media.values()}
assert len(c.sources)==3 and all(s['src'].startswith('data:video/mp4;base64,') for s in c.sources)
assert '@import' not in out and not re.search(r'url\(\s*[\"\x27]?https?://',out)
report={'single_html_file':name,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'external_resource_dependencies':0,'embedded_media':embedded_media,'embedded_documents':{k:{kk:vv for kk,vv in v.items() if kk!='text'} for k,v in embedded_documents.items()},'video_count':3,'media_payload_hashes_match_original':True,'validation':'HTML attributes checked; every embedded media base64 decoded and matched original SHA256; original MP4s previously decoded completely; browser execution not newly verified','delivery':'Send this HTML as a file; download and open it with a browser.'}
(D/'SINGLE_HTML_VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));shutil.copy2(target,W/name);shutil.copy2(D/'SINGLE_HTML_VERIFICATION.json',W/'SINGLE_HTML_VERIFICATION.json');shutil.copy2('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/make_professor_single_html.py',D/'build_single_html.py')
print('SINGLE_FILE',W/name,'BYTES',report['bytes'],'MEDIA',len(embedded_media),'DOCUMENTS',len(embedded_documents),'VIDEOS',len(c.sources),'EXTERNAL_DEPENDENCIES',0)
