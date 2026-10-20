"""Opt-in binary cache for unchanged robot-only XML models inside the source copy."""
from pathlib import Path
import hashlib,json,os,time
from common import ROOT,SOURCE
from model_binary_cache import sha
def install():
    import mujoco
    if getattr(mujoco,'_ihear_path_cache_installed',False):return
    cache=ROOT/'model_path_cache';cache.mkdir(exist_ok=True)
    assets={}
    for item in json.loads((ROOT/'audit/VENDOR_COPY_MANIFEST.json').read_text()):
        actual=sha(ROOT/item['copy'])
        if actual!=item['sha256']:raise RuntimeError('MODEL_ASSET_CHANGED')
        assets[item['copy']]=actual
    # Includes are part of the cache key; no caller-provided asset dictionaries.
    for path in SOURCE.rglob('*.xml'):assets[path.relative_to(ROOT).as_posix()]=sha(path)
    closure_hash=hashlib.sha256(json.dumps(assets,sort_keys=True).encode()).hexdigest()
    original=mujoco.MjModel.from_xml_path
    def load(filename,assets=None):
        path=Path(filename).resolve()
        if assets is not None or not path.is_relative_to(SOURCE):return original(filename,assets=assets)
        start=time.perf_counter();relative=path.relative_to(ROOT).as_posix()
        key=hashlib.sha256((relative+sha(path)+closure_hash+mujoco.__version__).encode()).hexdigest()
        binary=cache/(key+'.mjb');metadata=cache/(key+'.json');hit=binary.exists() and metadata.exists()
        if hit:
            record=json.loads(metadata.read_text())
            if sha(binary)!=record['mjb_sha256']:raise RuntimeError('ROBOT_BINARY_CACHE_HASH_MISMATCH')
            model=mujoco.MjModel.from_binary_path(str(binary))
        else:
            model=original(filename);mujoco.mj_saveModel(model,str(binary),None)
            record={'source':relative,'xml_sha256':sha(path),'asset_and_xml_closure_sha256':closure_hash,'mjb_sha256':sha(binary),'mujoco_version':mujoco.__version__,'bytes':binary.stat().st_size}
            metadata.write_text(json.dumps(record,indent=2))
        with (Path(os.environ['IHEAR_RUN_DIR'])/'MODEL_PATH_CACHE_EVENTS.jsonl').open('a') as f:
            f.write(json.dumps({'cache_hit':hit,'wall_s':time.perf_counter()-start,**record})+'\n')
        return model
    mujoco.MjModel.from_xml_path=staticmethod(load);mujoco._ihear_path_cache_installed=True
