"""Publish compact evidence derivatives, not raw archives or private host logs."""
from pathlib import Path
import json,hashlib,gzip,shutil,re,ast,subprocess
P=Path('/home/hank/coding/adaptive-traction-mpc-side-studies');W=P/'human-side-studies-closeout-v1';G=Path('/home/hank/coding/adaptive-traction-mpc-human-closeout-git');E=G/'side_studies/human_adaptation_r2_closeout_v1'
assert not E.exists();E.mkdir(parents=True)
aliases=[(str(P),'<SIDE_STUDIES_ROOT>'),('/home/hank/coding/adaptive-traction-mpc-learning','<PRIMARY_REPOSITORY>'),('/home/hank/coding/adaptive-traction-mpc-human-closeout-git','<ISOLATED_GIT_WORKSPACE>'),('/home/hank/envs/adaptive-online-v1','<PYTHON_ENVIRONMENT>'),('/mnt/d/CodexResearchEvidence/adaptive-traction-mpc-learning','<ARCHIVE_ROOT>'),('/mnt/c/Users/HankL','<WINDOWS_HOME_MOUNT>'),('C:\\\\Users\\\\HankL','<WINDOWS_HOME>'),('C:\\Users\\HankL','<WINDOWS_HOME>'),('/home/hank','<LINUX_HOME>')]
def redact(s):
 for a,b in aliases:s=s.replace(a,b)
 s=s.replace('HankL','<HOST_USER>').replace('D:/CodexResearchEvidence/adaptive-traction-mpc-learning','<WINDOWS_ARCHIVE_ROOT>')
 return s
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[];excluded=[]
def export(p,rel,kind='compact_evidence',canonical=False):
 dest=E/rel;dest.parent.mkdir(parents=True,exist_ok=True)
 if canonical:shutil.copyfile(p,dest);transformed=False
 elif p.suffix=='.gz':
  original=gzip.open(p,'rt').read();published=redact(original)
  with gzip.open(dest,'wt',compresslevel=3) as f:f.write(published)
  transformed=original!=published
 else:
  original=p.read_text();published=redact(original);dest.write_text(published);transformed=original!=published
 rows.append(dict(original_path=redact(str(p)),export_path=str(rel),original_sha256=sha(p),export_sha256=sha(dest),export_bytes=dest.stat().st_size,kind=kind,host_path_aliases_applied=transformed,scientific_numeric_values_changed=False))
# Single exact canonical source snapshot. All three local snapshots are identical at declared140 sources.
L=P/'lab-human-adaptation-contrast-v1';prov=json.loads((L/'SOURCE_PROVENANCE.json').read_text())
for rel,rec in prov['source_files'].items():
 src=L/'snapshot'/rel;assert sha(src)==rec['sha256'];export(src,Path('frozen_snapshot')/rel,'verified_frozen_source_or_config_asset',True)
 for name in ['human-size-contrast-v1','commissioning-to-recovery-geometry-compatibility-v1']:assert sha(P/name/'snapshot'/rel)==rec['sha256']
studies=['lab-human-adaptation-contrast-v1','human-size-contrast-v1','commissioning-to-recovery-geometry-compatibility-v1']
for name in studies:
 root=P/name
 for p in sorted(root.rglob('*')):
  if not p.is_file() or 'snapshot' in p.relative_to(root).parts:continue
  rel=p.relative_to(root)
  banned=p.is_symlink() or p.suffix=='.npz' or p.name.startswith(('model_consumption_','prediction_updates_','RESOURCE_SAMPLES','SAC_PHASE','TASK_PREDICTION_SAMPLES','learning_transitions')) or p.name=='runtime_artifacts.json.gz' or p.name=='USER_REQUEST.txt'
  # Direct host/process logs remain local; normalized summaries retained below.
  banned=banned or p.name.startswith('RESOURCE_OVERLAP_LOG') or p.name.startswith('RESOURCE_PREFLIGHT')
  if p.suffix=='.gz' and p.name!='summary.json.gz':banned=True
  if banned or p.suffix not in ['.json','.md','.csv','.py','.txt','.gz'] or p.stat().st_size>1100000:
   excluded.append(dict(path=redact(str(p)),sha256=sha(p),bytes=p.stat().st_size,reason='raw/trajectory/private-host-log or size-limited evidence retained locally/D, never uploaded'));continue
  export(p,Path('studies')/name/rel)
# Closeout scripts and migration evidence, excluding private main dirty-state capture.
for p in sorted(W.iterdir()):
 if not p.is_file() or p.name.startswith(('SAC_WORKTREE_BASELINE_PRIVATE','GIT_ISOLATION_SETUP','PUBLIC_EXPORT','GIT_RESULT','FINAL_MANIFEST')) or p.name in ['export_compact.py']:continue
 if p.suffix in ['.json','.md','.py']:export(p,Path('closeout')/p.name)
summary=json.loads((W/'RETENTION_SUMMARY.json').read_text());verification=json.loads((W/'ARCHIVE_VERIFICATION.json').read_text())
(E/'RESOURCE_AND_STORAGE_SUMMARY.json').write_text(json.dumps(dict(storage=summary,archive_verified_files=verification['verified_files'],all_decompressed_content_hashes_verified=verification['all_decompressed_content_hashes_verified'],key_restore_drill_count=len(verification['restore_drill']),new_simulations=0,new_controller_changes=0,SAC_worktree_git_untouched=True,private_process_and_user_request_logs_excluded=True),indent=2)+'\n')
(E/'SNAPSHOT_MAPPING.json').write_text(json.dumps(dict(shared_snapshot='frozen_snapshot',local_study_snapshots={n:'frozen_snapshot' for n in studies},all_declared140_files_identical=True,source_commit=prov['source_commit'],frozen_controller_and_config_assets_exact_bytes=True),indent=2)+'\n')
(E/'README.md').write_text("""# Human adaptation R2 — sealed evidence

Current conclusion and scope limits are in closeout/CLOSEOUT.md. This is a compact Git evidence export, not the complete raw backup. The 21-run success counts remain1/7,6/7,6/7. Installation support is limited to the discrete rho=.66 and .72 points. The existing oracle has a47.747426mm initial attachment difference and is not a same-state control. Height, combined factors and registered anatomy remain deferred.

frozen_snapshot contains the140 byte-identical verified source/config/assets shared by the three studies, including the old reference/scorer path. No production source is overwritten. Original environment versions, all cases/configs, all21 per-run summaries, model/parameter/paired evidence, historical reports/manifests and geometry-diagnostic evidence are under studies/. The old manifests describe original files; absent raw files in this Git export are preserved locally or in the D archive and enumerated by hash in PUBLIC_EXPORT_MANIFEST.json and the closeout migration index.

Host paths in compact metadata, archival scripts and study harness copies are replaced by explicit aliases for privacy. Source-to-export hash mapping records every transformation; scientific numbers and canonical frozen source/config bytes are unchanged. To reproduce a historical layout outside this sealed task, copy frozen_snapshot to each study's snapshot directory and bind <SIDE_STUDIES_ROOT>, <ARCHIVE_ROOT>, <PRIMARY_REPOSITORY>, <PYTHON_ENVIRONMENT>, <LINUX_HOME>, <WINDOWS_HOME_MOUNT> and <ISOLATED_GIT_WORKSPACE> to your local directories. The original runnable copies remain locally retained. No simulation is authorized or launched by this closeout.

closeout/RESTORE_INDEX.json maps original aliases to the D archive files, SHA256 of exact original bytes, decompressed gzip hashes or NPZ-member hashes, and recovery method. Bind the aliases before using closeout/restore_archive.py; it refuses overwrites and checks recovered contents. D also contains the original full nonredacted archive manifest/index and three key NPZ restore-drill files. Large runtime raw/NPZ files, archive packs, original user messages, host process logs and main-worktree private status are excluded from Git.

The original reports and manifests are retained unchanged locally. Exported copies with path aliases are distinct derivatives and do not retroactively alter those records. No merge, force push, RL, hardware, new Human matrix or controller update is part of this branch. STOP.
""")
# Mechanical validation only: parse/compile source without importing plant/controller.
for p in E.rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
for p in E.rglob('*.json'):json.loads(p.read_text())
for p in E.rglob('summary.json.gz'):json.loads(gzip.open(p,'rt').read())
assert len(list((E/'studies/lab-human-adaptation-contrast-v1/runs_R2').glob('*/summary.json.gz')))==21
violations=[]
for p in E.rglob('*'):
 if not p.is_file():continue
 assert p.suffix not in ['.npz','.tar','.zip'] and p.name!='runtime_artifacts.json.gz'
 if p.suffix in ['.py','.json','.md','.txt','.csv']:
  text=p.read_text()
  if any(x in text for x in ['-----BEGIN OPENSSH PRIVATE KEY-----','-----BEGIN RSA PRIVATE KEY-----','ghp_','github_pat_']) or re.search(r'\bsk-[A-Za-z0-9]{30,}\b',text):violations.append(str(p.relative_to(E)))
  assert '/home/hank' not in text and 'HankL' not in text
assert not violations,violations
manifest=dict(status='READY_FOR_EXPLICIT_FILE_GIT_STAGE',canonical_source_count=len(prov['source_files']),summary_count_R2=21,files=rows,excluded_files=excluded,privacy=dict(original_user_request_and_host_process_logs_excluded=True,private_main_git_status_excluded=True,host_paths_aliased=True,credential_literal_scan='PASS'),no_large_raw_or_archives=True,total_export_bytes=sum(p.stat().st_size for p in E.rglob('*') if p.is_file()))
(E/'PUBLIC_EXPORT_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
(W/'PUBLIC_EXPORT_SUMMARY.json').write_text(json.dumps(dict(status=manifest['status'],export_root=str(E),published_mapped_files=len(rows),excluded_files=len(excluded),source_count=140,R2_summary_count=21,bytes=manifest['total_export_bytes'],path_alias_derivatives=True,canonical_source_exact=True,privacy_scan='PASS',public_manifest_sha256=sha(E/'PUBLIC_EXPORT_MANIFEST.json')),indent=2)+'\n')
print('PUBLIC_EXPORT',len(rows),'MiB',manifest['total_export_bytes']/1048576,'EXCLUDED',len(excluded),'R2_SUMMARIES',21,'SOURCE_HASHES',140)
