"""Publish a scientific-only pilot readiness alias from immutable detailed gate.

PASS never means full host timing, hardware or real-time qualification. The
original detailed status and exact source hash remain embedded and authoritative.
"""
import argparse
import json
import hashlib
import os
from pathlib import Path
from evidence_io import read_json,file_sha


def publish(source,output,archive_previous=None):
    detail=read_json(source)
    previous=None
    if output.exists():
        if archive_previous is None:raise FileExistsError(output)
        if archive_previous.exists():raise FileExistsError(archive_previous)
        previous=output.read_bytes()
        archive_previous.parent.mkdir(parents=True,exist_ok=True)
        with archive_previous.open('xb') as stream:stream.write(previous)
    result=dict(detail)
    result['detailed_computation_status']=detail['status']
    result['status']='PASS' if detail.get('ready_for_small_scientific_pilot') else 'FAIL'
    result['pass_scope']='small Scientific Simulation pilot only; algorithm plausible path plus clean normal validity; full wall budget and hardware qualification are independent'
    config=detail['selected_configuration']
    indices=config.get('proposal_source_indices')
    if not indices:raise ValueError('explicit actually profiled proposal subset required')
    result['pilot_configuration']={'legacy_candidate_limit':config['legacy_candidate_limit'],
                                   'proposal_indices':indices,
                                   'proposal_bank_source_indices':indices,
                                   'lazy_legacy_comparator_on_committed':config.get('lazy_legacy_comparator_on_committed',False)}
    result['detailed_gate_source']={'path':str(source),'original_content_sha256':file_sha(source)}
    result['automatic_hard_deadline_qualification']=False
    if previous is not None:result['supersedes_preserved_publication']={'path':str(archive_previous),'sha256':hashlib.sha256(previous).hexdigest()}
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.name+'.new')
    with temporary.open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    os.replace(temporary,output)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--archive-previous',type=Path,help='preserve exact old publication before atomic update')
    args=parser.parse_args()
    result=publish(args.source,args.output,args.archive_previous)
    print(json.dumps({k:result[k] for k in ('status','detailed_computation_status','ready_for_small_scientific_pilot','pilot_configuration','observed_full_host_spans_within_architecture_opportunity')}))
