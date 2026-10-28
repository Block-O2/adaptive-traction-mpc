"""SOURCE_ONLY frozen new-parameter continuous ILC/BO entrypoint; separate protocol required."""
from pathlib import Path
import os,sys,json,time,hashlib
P=Path(os.environ['ACL2_PACKAGE'])
sys.path.insert(0,str(P/'families/history_conditioned'))
from continuous_ilc_worker_v4 import main
if __name__=='__main__':
    binary=Path(sys.executable).resolve()
    identity={'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'created_unix':time.time(),'python_executable':sys.executable,'python_binary_resolved':str(binary),'python_binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'numpy_version':sys.modules['numpy'].__version__,'source':str(Path(__file__).relative_to(P)),'scope':'Actual imported interpreter and numeric environment before first persistent physics START'}
    config=json.loads((P/sys.argv[1]).read_text())
    dest=P/'audit'/(config['group']+'_INTERPRETER.json');assert not dest.exists()
    dest.write_text(json.dumps(identity,indent=2)+'\n')
    main()
