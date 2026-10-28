"""Refresh explicit genuine metadata after reviews close; never fake old ENDs."""
from pathlib import Path
import copy
import hashlib
import json
import time

P = Path(__file__).resolve().parents[1]
BASE = P / 'agent_reviews/final_metadata_inventory'


def sha(f):
    return hashlib.sha256(f.read_bytes()).hexdigest()


def read(relative):
    return json.loads((P / relative).read_text())


def put(relative, value):
    with (P / relative).open('x') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


reviews = read('agent_reviews/final_metadata_inventory/REVIEW_INVENTORY_CANDIDATE.json')['agent_reviews']
reviews += read('audit/review_closure_adapters_v1/ADAPTER_INDEX.json')['agent_reviews']
extras = [
    ('agent_reviews/final_metadata_inventory', 'END.json', 'OUTPUT_MANIFEST.json'),
    ('agent_reviews/final_verifier_devpc01_v4', 'END.json', 'OUTPUT_MANIFEST.json'),
    ('agent_reviews/final_scientific_claim_scope', 'END.json', 'OUTPUT_MANIFEST.json'),
    ('agent_reviews/integral_audit/incremental_closed_v2', 'END.json', 'MANIFEST.json'),
    ('agent_reviews/integral_audit/incremental_final_lstf_v3', 'END.json', 'MANIFEST.json'),
]
for directory, end, manifest in extras:
    assert (P / directory / end).exists() and (P / directory / manifest).exists(), 'REVIEW_NOT_CLOSED:' + directory
    reviews.append({'directory': directory, 'end': directory + '/' + end, 'manifest': directory + '/' + manifest})
assert len(reviews) == len({r['directory'] for r in reviews})
actual_top = {str(d.relative_to(P)) for d in (P / 'agent_reviews').iterdir() if d.is_dir()}
assert actual_top <= {r['directory'] for r in reviews}, 'REVIEW_DIRECTORY_OMITTED'

inventory = copy.deepcopy(read('agent_reviews/final_metadata_inventory/OWNERSHIP_METADATA_INVENTORY_CANDIDATE.json'))
files = {r['path']: r for r in inventory['metadata_files']}
refresh = []
for rel, row in files.items():
    f = P / rel
    assert f.is_file(), 'DECLARED_METADATA_MISSING:' + rel
    current = sha(f)
    if rel.startswith('owned/'):
        if row.get('sha256') != current:
            refresh.append({'path': rel, 'prior_candidate_sha256': row.get('sha256'), 'final_sha256': current,
                            'scope': 'Declared root-owned mutable lifecycle record refreshed after task closure'})
        row['sha256'] = current
    elif row.get('sha256'):
        assert row['sha256'] == current, 'SEALED_REVIEW_METADATA_CHANGED:' + rel


def add_metadata(f, origin, selectors='canonical_genuine_metadata'):
    rel = str(f.relative_to(P))
    assert f.is_file()
    files[rel] = {'path': rel, 'sha256': sha(f), 'origin': origin, 'selectors': selectors}


for directory, end, manifest in extras:
    D = P / directory
    add_metadata(D / end, 'NEW_SEALED_REVIEW_CURRENT_END')
    add_metadata(D / manifest, 'NEW_SEALED_REVIEW_MANIFEST', [])
    # Only top-level receipts, and explicit real test-harness boundaries. Never
    # recursively inspect their nested synthetic fixture/owned/result payloads.
    for f in D.glob('*.json'):
        if f.name.endswith('_START.json') or f.name.endswith('_END.json') or f.name in ['START.json', 'OWNED_PROCESS_AUDIT.json', 'OWNED_FINAL_CHECK.json']:
            add_metadata(f, 'NEW_REVIEW_REAL_BOUNDARY_RECEIPT')
    for pattern in ['pure_fixture*/START.json', 'pure_fixture*/END.json']:
        for f in D.glob(pattern):
            add_metadata(f, 'HARNESS_REAL_PROCESS_BOUNDARY_NOT_NESTED_SYNTHETIC')

for r in read('audit/review_closure_adapters_v1/ADAPTER_INDEX.json')['agent_reviews']:
    if r['end'].startswith('audit/'):
        add_metadata(P / r['end'], 'CURRENT_MAIN_CLOSURE_RECEIPT_NOT_ORIGINAL_END')
for name in ['START.json', 'END.json']:
    add_metadata(P / 'analysis/figures_final_v3' / name, 'FINAL_FIGURE_REAL_PROCESS_BOUNDARY')

# Preserve only explicit top-level/main-owned identity pointers in root audit
# and analysis JSON. Their numerical contents are never features/policy inputs.
# No recursive synthetic pid discovery and no inference of absent identity.
aliases = [('pid', 'start_ticks'), ('pid', 'recorded_start_ticks')]
for folder in ['audit', 'analysis']:
    for f in (P / folder).glob('*.json'):
        if f.stat().st_size > 8 * 2**20:
            continue
        try:
            data = json.loads(f.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        selectors = []
        for pointer in ['', '/process', '/owned', '/identity', '/current_main_metadata_process']:
            obj = data if not pointer else data.get(pointer[1:])
            if not isinstance(obj, dict):
                continue
            for pk, tk in aliases:
                if pk in obj and tk in obj and type(obj[pk]) is int and (type(obj[tk]) is int or isinstance(obj[tk], str) and obj[tk].isdigit()):
                    selectors.append({'pointer': pointer, 'pid_key': pk, 'ticks_key': tk})
        if selectors:
            add_metadata(f, 'EXPLICIT_MAIN_INLINE_IDENTITY_POINTERS_ONLY', selectors)

inventory.update(metadata_files=list(files.values()), review_directories=sorted(actual_top), pending_review=[],
                 created_unix=time.time(), main_refreshed_after_all_reviews_closed=True,
                 root_lifecycle_refresh=refresh,
                 limitations=inventory.get('limitations', []) + [
                     'Original history/local_surrogate ENDs remain absent; current main receipts are explicit adapters only.',
                     'Legacy string ticks are read with strict encoding normalization; original bytes not changed.',
                     'Foreground static/metadata tool-only PID gaps and unpaired original END records are not repaired.',
                 ], source_sha256=sha(Path(__file__)))
put('audit/ACTUAL_FINAL_OWNERSHIP_INVENTORY_V2.json', inventory)
put('audit/FINAL_REVIEW_INDEX_V2.json', {'agent_reviews': reviews, 'top_level_directories': sorted(actual_top),
                                     'original_missing_ENDs_and_nonstandard_manifests_acknowledged': True,
                                     'metadata_perfect_PASS_allowed': False, 'created_unix': time.time()})
pairdoc = read('agent_reviews/final_metadata_inventory/OWNED_END_PAIRS_V3_CANDIDATE.json')
pairs = pairdoc.get('owned_end_pairs', pairdoc.get('pairs'))
assert isinstance(pairs, list), 'EXPLICIT_OWNED_PAIR_SCHEMA_REQUIRED'
put('audit/FINAL_OWNED_PAIR_BASE_V2.json', {'owned_end_pairs': pairs, 'not_independent_task_counts': True,
                                       'scope': 'Original literal-int genuine identity intersections; fresh root-owned pairs added by final evidence builder.'})
print('FINAL_METADATA_INVENTORY', len(actual_top), 'top reviews', len(reviews), 'review records', len(files), 'metadata files')
