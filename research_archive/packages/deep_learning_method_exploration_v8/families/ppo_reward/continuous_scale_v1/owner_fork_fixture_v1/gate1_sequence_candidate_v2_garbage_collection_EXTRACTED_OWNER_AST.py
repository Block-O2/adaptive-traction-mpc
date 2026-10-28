def canonical(value):
    return json.loads(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False))

def _synthetic_extracted_owner_generator(sentinel):
    owner_pid = os.getpid()
    owner_start_ticks = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])

    def assert_owner():
        if os.getpid() != owner_pid:
            raise GeneratorExit('FORK_CHILD_HAS_NO_SHARED_GENERATOR_WRITE_AUTHORITY')

    def put(relative, payload):
        assert_owner()
        original_put(relative, payload)

    def save_status(stage, **extra):
        put('OWNER_CANCEL_EVIDENCE', {'stage': stage, 'sentinel': sentinel, 'extra': extra, 'synthetic_only': True})

    def save(stage):
        put('OWNER_CANCEL_EVIDENCE', {'stage': stage, 'sentinel': sentinel, 'synthetic_only': True})
    try:
        put('READY_EVIDENCE', {'stage': 'SYNTHETIC_PENDING_BEFORE_FORK', 'sentinel': sentinel, 'synthetic_only': True})
        yield put
    except GeneratorExit:
        if os.getpid() != owner_pid:
            return
        save_status('OWNER_GENERATOR_CLOSED_PRESERVE_ALREADY_CAPTURED_EVIDENCE', root_must_reconcile_ANY_started_child_not_captured=True)
        return
