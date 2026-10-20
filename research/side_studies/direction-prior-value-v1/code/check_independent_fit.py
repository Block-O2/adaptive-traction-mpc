"""Verify exact reuse of development protocol and absence of held-out labels."""
from freeze import *
def main():
 a=json.loads((STUDY/'weights_v2_seed2026100602/TRAINING.json').read_text())
 b=json.loads((STUDY/'weights_v2_seed2026100603/TRAINING.json').read_text())
 keys=('version','network_hidden','G_heads','V_label','continuation','feature_semantics','data_sources','group_splits','representation_deduplication','V_counts','G_counts','training_script_sha256','inference_source_sha256')
 equal={key:a[key]==b[key] for key in keys};assert all(equal.values())
 assert a['seed']!=b['seed'] and not a['test_used'] and not b['test_used']
 assert all(Path(p).name.startswith(('parent_train_','parent_dev_','020_parent_train_1_')) for p in b['data_sources'])
 assert all(sha(Path(p))==h for p,h in b['data_sources'].items())
 result=dict(status='PASS',same_protocol_fields=equal,distinct_initialization_seeds=[a['seed'],b['seed']],heldout_sources_used=False,development_source_files=len(b['data_sources']),device=b['device'],wall_s=b['wall_s'],peak_host_rss_bytes=b['peak_host_rss_bytes'],CUDA_peak_allocated_bytes=b['CUDA_peak_allocated_bytes'],weights_sha256=b['weights_sha256'],training_script_sha256=b['training_script_sha256'])
 save(STUDY/'INDEPENDENT_FIT_VERIFICATION.json',result);print(json.dumps(result))
if __name__=='__main__':main()
