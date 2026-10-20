from pathlib import Path
import sys,os,json,hashlib,time
P=Path(__file__).resolve().parents[1]
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',MPLCONFIGDIR=str(P/'tmp/mpl'),TMPDIR=str(P/'tmp'))
sys.dont_write_bytecode=True;sys.path.insert(0,str(P/'code'));sys.path.insert(0,str(P/'prototype'))
import study_common as sc
import runner,rich_planner
files=[]
for name,module in list(sys.modules.items()):
 f=getattr(module,'__file__',None)
 if f and ('/home/hank/coding/' in f):files.append(dict(module=name,file=f,sha256=hashlib.sha256(Path(f).read_bytes()).hexdigest()))
foreign=[r for r in files if not Path(r['file']).resolve().is_relative_to(P)]
assert not foreign,foreign
case,options=sc.load_case_options()
(P/'audit/IMPORT_PREFLIGHT.json').write_text(json.dumps(dict(status='PASS',unix=time.time(),closure=files,foreign_research_imports=foreign,torch_imported='torch' in sys.modules,case=sc.clean(case),options=sc.clean(options)),indent=2))
print('IMPORT_PREFLIGHT',len(files),'torch','torch' in sys.modules)
