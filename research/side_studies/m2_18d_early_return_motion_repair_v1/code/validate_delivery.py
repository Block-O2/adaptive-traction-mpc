"""Independent file/hash/link and scientific denominator checks on exported bytes."""
from task_bootstrap import *
import re
TARGET=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1/delivery')
def read(name):return json.loads((TARGET/name).read_text())
def main():
 final='--final' in sys.argv;issues=[];manifest=read('DELIVERY_MANIFEST.json');entries=manifest['entries'];seen=set()
 for row in entries:
  rel=row['relative_path'];p=TARGET/rel
  if rel in seen:issues.append('DUPLICATE_MANIFEST:'+rel)
  seen.add(rel)
  if not p.is_file():issues.append('MISSING:'+rel);continue
  if sha(p)!=row['sha256'] or p.stat().st_size!=row['bytes']:issues.append('BYTES_CHANGED:'+rel)
  if p.suffix=='.json':
   try:json.loads(p.read_text())
   except Exception as e:issues.append('INVALID_JSON:'+rel+':'+str(e))
 excluded={'DELIVERY_MANIFEST.json','DELIVERY_EXPORT_MANIFEST.json','DELIVERY_VALIDATION.json'}
 extra=[str(p.relative_to(TARGET)) for p in TARGET.rglob('*') if p.is_file() and str(p.relative_to(TARGET)) not in seen and p.name not in excluded]
 if extra:issues.extend('UNMANIFESTED:'+p for p in extra)
 if read('DELIVERY_EXPORT_MANIFEST.json')!=manifest:issues.append('EXPORT_MANIFEST_DISAGREES')
 links=0
 for name in ('REPORT.md','SOURCE_GUIDE.md'):
  text=(TARGET/name).read_text()
  for raw in re.findall(r'\]\(<([^>]+)>\)',text):
   if raw.startswith(('http:','https:')):continue
   numbered=re.search(r':(\d+)$',raw);raw=re.sub(r':\d+$','',raw);p=Path('/mnt/c/'+raw[3:]) if raw.startswith('C:/') else Path(raw)
   links+=1
   if not p.is_file():issues.append('BROKEN_LINK:'+name+':'+raw)
   elif numbered and not 1<=int(numbered.group(1))<=len(p.read_text().splitlines()):issues.append('BAD_SOURCE_LINE:'+name+':'+raw)
 report=(TARGET/'REPORT.md').read_text();sections=re.findall(r'^## (\d+)\.',report,re.M)
 if sections!=list(map(str,range(1,14))):issues.append('REPORT_SECTIONS')
 compute=read('evidence/reports/AUDIT_COMPUTE_RECONCILIATION.json');host=read('evidence/reports/HOST_QUALIFICATION_SUMMARY.json');raw=read('evidence/reports/RAW_PHYSICS_PROVENANCE_AUDIT.json');selection=read('evidence/reports/FROZEN_SELECTION_INTEGRITY.json');legal=read('evidence/reports/LEGAL_PREFIX_STABILITY_SUMMARY.json');suffix=read('evidence/reports/SUFFIX_LABEL_AUDIT.json');closure=read('evidence/reports/SOURCE_CLOSURE_AUDIT.json')
 if compute['attempts']!=compute['ended'] or compute['active_ids'] or compute['attempts']>160:issues.append('ATTEMPT_CLOSEOUT')
 if not compute['raw_count_verification_complete'] or raw['status']!='PASS' or raw['attempts_audited']!=compute['attempts'] or raw['without_saved_artifact']:issues.append('RAW_COVERAGE')
 if compute['authoritative_total_actual_new_native_steps']!=raw['native_steps_audited']+sum(r['inter_rep_native_steps'] for r in compute['rows']):issues.append('RAW_TOTAL')
 if host['attempts']!=len(host['rows']) or host['task_activated_count']!=sum(r['task_activated'] for r in host['rows']) or host['task_activated_over55_count']!=sum(r['task_over55'] for r in host['rows']):issues.append('HOST_DENOMINATORS')
 if host['valid_complete_tasks'] or host['learning_execution_proven_count'] or host['timely_learning_execution_proven_count']:issues.append('UNEXPECTED_HOST_POSITIVE_REVIEW_REQUIRED')
 if selection['status']!='PASS' or selection['issues'] or selection['Q_updates'] or suffix['aggregate']['labels_used_for_training']:issues.append('FROZEN_Q_OR_LABEL_INTEGRITY')
 if legal['valid_pairs']!=8 or legal['positive_pairs']!=8 or len({r['seed'] for r in legal['rows']})!=8 or any(r['matched_pre_learning_prefix_proof']['status']!='PASS' for r in legal['rows']):issues.append('LEGAL_PREFIX_PROTOCOL')
 if closure['issues'] or closure['top_level_overlap_rows'] or closure['unretained_declared_sources'] or closure['attempts']!=compute['attempts']:issues.append('SOURCE_CLOSURE')
 if final:
  close=read('evidence/reports/CLOSEOUT_STATUS.json');fig=read('FIGURE_MANIFEST.json');preserve=read('evidence/reports/PRESERVATION_AUDIT.json');data=read('evidence/reports/TOTAL_DATA_ACCOUNTING.json')
  if close['status']!='STOPPED_AND_RECONCILED' or 'DRAFT' in report:issues.append('FINAL_NOT_CLOSED')
  if fig['status']!='VISUALLY_VERIFIED':issues.append('FIGURE_VISUAL_QA_REQUIRED')
  approved=fig.get('visual_review_approved_hashes',{})
  if len(fig['figures'])!=6 or len(approved)!=6:issues.append('FIGURE_QA_SET')
  for row in fig['figures']:
   name=Path(row['path']).name;p=TARGET/'figures'/name
   if not p.is_file() or sha(p)!=row['sha256'] or approved.get(name)!=row['sha256']:issues.append('FIGURE_QA_BYTES:'+name)
  for name,digest in fig['inputs'].items():
   rel=Path(name).relative_to(STUDY)
   p=TARGET/'evidence'/rel.name if rel.parts[0]=='output' else TARGET/'evidence'/rel
   if not p.is_file() or sha(p)!=digest:issues.append('FIGURE_INPUT_BYTES:'+str(rel))
  plan=read('evidence/RUN_PLAN.json');checkpoint=read('evidence/CHECKPOINT.json');runner=read('evidence/RUNNER_STOP.json')
  if plan.get('phase')!='CLOSED' or not plan.get('dispatch_disabled') or plan.get('auto_resume') is not False or not (TARGET/'evidence/STOP_DISPATCH').is_file():issues.append('DISPATCH_CLOSEOUT')
  if not close.get('runner_exit_verified') or close.get('remaining_owned_python_processes') or close.get('pending_queue') or close.get('active_physics') or not 7<=close['elapsed_h']<9:issues.append('OWNER_CLOSEOUT')
  if checkpoint.get('status')!='STOPPED_AND_RECONCILED' or checkpoint.get('active') or checkpoint.get('auto_resume') is not False or runner['attempts']!=compute['attempts']:issues.append('CHECKPOINT_CLOSEOUT')
  processes=read('evidence/reports/KNOWN_PROCESS_CLOSEOUT_AUDIT.json')
  if processes['status']!='ALL_RECORDED_OWNED_IDENTITIES_ABSENT' or processes['unexpected_live_recorded_identities'] or processes['allowed_monitor']:issues.append('KNOWN_PROCESS_CLOSEOUT')
  if preserve['status']!='PASS' or not preserve['Q_weights_equal']:issues.append('PRESERVATION')
  if data['total_added_bytes_conservative']>=10*2**30:issues.append('DATA_BUDGET')
 out=dict(status='PASS' if not issues else 'FAIL',final=final,created_unix=time.time(),manifest_sha256=sha(TARGET/'DELIVERY_MANIFEST.json'),files_checked=len(entries),bytes_checked=sum(r['bytes'] for r in entries),local_links_checked=links,report_sections=len(sections),physics_attempts=compute['attempts'],host_attempts=host['attempts'],authoritative_native_steps=compute['authoritative_total_actual_new_native_steps'],issues=issues,manifest_self_files_excluded=sorted(excluded),physics_added=0)
 save(TARGET/'DELIVERY_VALIDATION.json',out);print(json.dumps(out));assert not issues
if __name__=='__main__':main()
