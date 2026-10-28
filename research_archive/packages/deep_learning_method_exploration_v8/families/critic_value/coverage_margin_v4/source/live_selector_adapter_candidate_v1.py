"""SOURCE_ONLY A4冻结主法/原classifier/39强规则，实际OUT0来源证明。"""
from pathlib import Path
import hashlib
import importlib.util
import json
ROOT_REL='families/critic_value/coverage_margin_v4'
SELECTORS=['A4_PRIMARY_MARGIN45','A4_ORIGINAL_CLASSIFIER39','A4_CONTROL_B','A4_CONTROL_BEST_FIXED','A4_CONTROL_IF_STUMP','A4_CONTROL_NEAREST']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def predict_before_B(package,config,study):
 P=Path(package).resolve();mp=P/ROOT_REL/'LIVE_ADAPTER_MANIFEST_V1.json';manifest=load(mp);assert sha(__file__)==manifest['adapter_sha256'] and manifest['selectors']==SELECTORS
 def document(item):
  p=(P/item['path']).resolve();assert p.is_relative_to(P) and sha(p)==item['sha256'];return load(p)
 bundle=document(manifest['bundle']);a3=document(manifest['proof_bundle'])
 adapter_path=(P/manifest['proof_adapter']['path']).resolve();assert sha(adapter_path)==manifest['proof_adapter']['sha256']
 spec=importlib.util.spec_from_file_location('_a4_frozen_actual_source_gate',adapter_path);proof_adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof_adapter)
 assert bundle['menu']==a3['menu'];proof_adapter._menu_matches(P,config,bundle['menu'])
 raw,proof,proof_audit=proof_adapter._actual_live_proof(P,config,study,a3)
 api=proof_adapter._private_modules(P,manifest['api_files'],'A4')['predict_api']
 predictions={'A4_PRIMARY_MARGIN45':api.predict(bundle,raw,'ABS','ENSEMBLE45_002','JF_QUALIFIED',source_proof=proof),'A4_ORIGINAL_CLASSIFIER39':api.predict(bundle,raw,'ABS','CLASSIFIER39','JF_QUALIFIED',source_proof=proof)}
 for name,control in [('A4_CONTROL_B','CONSTANT_B'),('A4_CONTROL_BEST_FIXED','BEST_FIXED'),('A4_CONTROL_IF_STUMP','IF_STUMP'),('A4_CONTROL_NEAREST','NEAREST')]:predictions[name]=api.predict_control(bundle,raw,control,'JF_QUALIFIED',source_proof=proof)
 assert list(predictions)==SELECTORS and not study.metrics
 decisions={name:proof_adapter._with_fallback(pred,bundle['menu']) for name,pred in predictions.items()}
 return {'schema':'v8.a4.frozen_pre_B_live_decisions.v1','primary':'A4_PRIMARY_MARGIN45','decisions':decisions,'actual_source_proof':proof,'proof_audit':proof_audit,'all_choices_before_any_B_result':True,'API_calls':{'A4_model':2,'inherited_A3_control':4},'new_fit_physics':0,'same_selected_recipe_sharing_not_independent_or_savings':True,'bundle_sha256':manifest['bundle']['sha256'],'adapter_sha256':manifest['adapter_sha256'],'adapter_manifest_sha256':sha(mp)}
