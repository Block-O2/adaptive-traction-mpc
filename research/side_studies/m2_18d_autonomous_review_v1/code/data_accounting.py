"""Conservative logical file-byte accounting of both new package directories."""
from task_bootstrap import *
LOCAL=Path('/mnt/c/Users/HankL/Desktop/Coding/adaptive_traction_mpc/b_native_q_realtime_integration_v1')
def count(root):
 sizes={};files=0
 for p in root.rglob('*'):
  if p.is_file():
   files+=1;part=p.relative_to(root).parts[0];sizes[part]=sizes.get(part,0)+p.stat().st_size
 return dict(path=str(root),files=files,total_bytes=sum(sizes.values()),bytes_by_directory=sizes)
def main():
 wsl=count(STUDY);windows=count(LOCAL);total=wsl['total_bytes']+windows['total_bytes']
 out=dict(status='PASS' if total<10*2**30 else 'FAIL',measured_unix=time.time(),WSL_new_study=wsl,Windows_new_authoring_and_delivery=windows,total_added_bytes_conservative=total,max_added_bytes=10*2**30,logical_file_bytes_not_allocated_disk_blocks=True,duplicated_delivery_and_source_copies_counted_in_both_locations=True,initial_frozen_source_copies_included=True,excluded_old_study_and_primary=True,scope_note='Point-in-time bytes of both new package directories. Small later report, accounting and export manifests add bytes; final delivered measurement states its time explicitly. Raw physics files are frozen after159 ENDs.')
 save(STUDY/'reports/TOTAL_DATA_ACCOUNTING.json',out);print(json.dumps(dict(status=out['status'],WSL_bytes=wsl['total_bytes'],Windows_bytes=windows['total_bytes'],total_bytes=total,total_GiB=total/2**30)));assert out['status']=='PASS'
if __name__=='__main__':main()
