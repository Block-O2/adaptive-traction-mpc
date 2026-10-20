"""Opt-in fresh-clone audit hook, including subprocesses in the fresh venv.

Set IHEAR_FORBIDDEN_ROOTS to a JSON list, IHEAR_ACCESS_GUARD_LOG to a new log.
install_access_guard.py installs this file under a unique .pth module name
to avoid system sitecustomize shadowing. Use only disposable environments.
This is a Python file-access guard, not an OS filesystem sandbox.
"""
import json
import os
import sys

_roots = tuple(os.path.realpath(p) for p in json.loads(os.environ.get('IHEAR_FORBIDDEN_ROOTS', '[]')))
_log = os.environ.get('IHEAR_ACCESS_GUARD_LOG')


def _guard(event, args):
    if event not in {'open', 'os.listdir', 'os.scandir', 'os.chdir'} or not args:
        return
    path = args[0]
    if not isinstance(path, (str, bytes, os.PathLike)):
        return
    actual = os.path.realpath(os.fsdecode(path))
    if any(actual == root or actual.startswith(root + os.sep) for root in _roots):
        if _log:
            with open(_log, 'a') as stream:
                stream.write(json.dumps(dict(event=event, path=actual, pid=os.getpid())) + '\n')
        raise PermissionError('FRESH_CLONE_FORBIDS_LEGACY_ROOT:' + actual)


if _roots:
    sys.addaudithook(_guard)
