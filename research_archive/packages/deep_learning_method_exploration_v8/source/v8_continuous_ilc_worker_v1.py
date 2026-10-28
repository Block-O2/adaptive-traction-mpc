"""Main-owned isolated entry. The family worker enforces persistent B gate."""
from pathlib import Path
import os,sys,json,hashlib,platform,time
P=Path(os.environ['ACL2_PACKAGE']).resolve();sys.dont_write_bytecode=True
sys.path.insert(0,str(P/'families/history_conditioned'))
from continuous_ilc_worker_v1 import main
if __name__=='__main__':
    config=json.loads((P/sys.argv[1]).read_text());group=config['group']
    import numpy as np
    executable=Path(sys.executable).resolve();output=P/'jobs'/group/'ENVIRONMENT_BEFORE_PHYSICS.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:
        json.dump({'unix':time.time(),'python_executable':sys.executable,'resolved_python_binary':str(executable),'python_binary_sha256':hashlib.sha256(executable.read_bytes()).hexdigest(),'python_version':platform.python_version(),'numpy_version':np.__version__,'pid':os.getpid(),'start_ticks':int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),'loaded_source_files':{name:str(Path(module.__file__).resolve()) for name,module in list(sys.modules.items()) if getattr(module,'__file__',None) and Path(module.__file__).is_file()},'new_physics_so_far':0},stream,indent=2);stream.write('\n')
    main()
