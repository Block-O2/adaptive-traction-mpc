"""Optional content-addressed MuJoCo compiled model cache; never changes XML."""
from pathlib import Path
import json,hashlib,time,os
from common import ROOT
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def install():
    import mujoco
    if getattr(mujoco,'_ihear_binary_cache_installed',False):return
    cache=ROOT/'model_cache';cache.mkdir(exist_ok=True)
    assets={}
    for x in json.loads((ROOT/'audit/VENDOR_COPY_MANIFEST.json').read_text()):
        actual=sha(ROOT/x['copy'])
        if actual!=x['sha256']:raise RuntimeError('MODEL_ASSET_CHANGED')
        assets[x['copy']]=actual
    asset_key=hashlib.sha256(json.dumps(assets,sort_keys=True).encode()).hexdigest()
    original=mujoco.MjModel.from_xml_string
    def load(xml,assets=None):
        if assets is not None:return original(xml,assets=assets)
        start=time.perf_counter();key=hashlib.sha256((xml+mujoco.__version__+asset_key).encode()).hexdigest()
        binary=cache/(key+'.mjb');metadata=cache/(key+'.json')
        hit=binary.exists() and metadata.exists()
        if hit:
            record=json.loads(metadata.read_text())
            if sha(binary)!=record['mjb_sha256']:raise RuntimeError('MODEL_BINARY_CACHE_HASH_MISMATCH')
            model=mujoco.MjModel.from_binary_path(str(binary))
        else:
            model=original(xml);mujoco.mj_saveModel(model,str(binary),None)
            record={'xml_sha256':hashlib.sha256(xml.encode()).hexdigest(),'mjb_sha256':sha(binary),'vendor_assets_sha256':asset_key,'mujoco_version':mujoco.__version__,'bytes':binary.stat().st_size}
            metadata.write_text(json.dumps(record,indent=2))
        out=Path(os.environ['IHEAR_RUN_DIR'])/'MODEL_CACHE_EVENTS.jsonl'
        with out.open('a') as f:f.write(json.dumps({'key':key,'cache_hit':hit,'wall_s':time.perf_counter()-start,**record})+'\n')
        return model
    # Pybind class assignment is tested by the guarded first build. If this
    # binding is immutable, fail closed instead of editing the physical source.
    mujoco.MjModel.from_xml_string=staticmethod(load)
    mujoco._ihear_binary_cache_installed=True
