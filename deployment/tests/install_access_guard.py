"""Install an opt-in access hook in a disposable venv using a unique .pth import.

System sitecustomize can precede venv site-packages. A unique .pth module avoids
that shadowing; the guard still activates only with IHEAR_FORBIDDEN_ROOTS set.
"""
from pathlib import Path
import shutil
import sys
import sysconfig

if sys.prefix == sys.base_prefix:
    raise SystemExit('Refuse to install test hooks outside a disposable virtual environment')
site = Path(sysconfig.get_paths()['purelib'])
module = site / '_ihear_fresh_clone_guard.py'
pth = site / 'ihear_fresh_clone_guard.pth'
if module.exists() or pth.exists():
    raise SystemExit('Access hook already exists; use a fresh environment')
shutil.copyfile(Path(__file__).with_name('sitecustomize.py'), module)
pth.write_text('import _ihear_fresh_clone_guard\n')
print('ACCESS_GUARD_INSTALLED', pth)
