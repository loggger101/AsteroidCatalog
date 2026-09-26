# -*- coding: utf-8 -*-
"""What several test files need: the checkout, a clean interpreter, the tools.

pytest puts this directory on `sys.path` (its default "prepend" import mode),
so a test imports it as `from _support import ...`.
"""

import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_env(**overrides):
    """`os.environ` with this checkout first on PYTHONPATH, for a subprocess.

    A subprocess is how a test sees a CLEAN interpreter: by the time a test
    runs, pytest has already imported the package.  Pass NAME=None to unset.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
    for name, value in overrides.items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def load_tool(name):
    """Import `tools/<name>.py` as a module; `tools/` is not a package."""
    path = os.path.join(REPO, "tools", name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
