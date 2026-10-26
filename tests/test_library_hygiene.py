# -*- coding: utf-8 -*-
"""Importing this package writes nothing, anywhere.

THE ORIGINAL DID BOTH, AND WAS RIGHT TO.  A pipeline stage that is also the
program should print its configuration and make the directory it is about to
write to.  A library imported to read one taxonomy row should do neither, and
the difference is the only reason `config.py` was adapted rather than sliced
whole.

These are the claims that adaptation makes, run as tests, because a claim
about a side effect is exactly the kind nothing else here would catch: the
package works perfectly either way.
"""

import os
import subprocess
import sys

from _support import REPO, repo_env
from samebytes import source

# The output-directory override must not leak in from the developer's shell.
_CLEAN = {"ASTEROID_CATALOG_OUTPUT_DIR": None}


def _run(code, cwd):
    """Import in a CLEAN interpreter.

    It has to be a subprocess: by the time a test runs, pytest has already
    imported the package, so an in-process check would be asking whether an
    import that already happened is about to print.
    """
    return subprocess.run([sys.executable, "-c", code], cwd=str(cwd),
                          capture_output=True, text=True,
                          env=repo_env(ASTEROID_CATALOG_OUTPUT_DIR=None))


def test_import_prints_nothing():
    """`samebytes.source.quiet_import`: exit 0, nothing on stdout or stderr."""
    assert source.quiet_import(REPO, "import asteroid_catalog", env=_CLEAN) == ([], 1)


def test_import_creates_no_directory():
    """The original made the output dir AND the download cache dir at import.

    Either is a library with a side effect; the cache one is worse, because it
    lands in the system temp directory of a machine that only wanted a
    constant.
    """
    assert source.quiet_import(REPO, "import asteroid_catalog as ac; ac.CONFIG.output_dir",
                               env=_CLEAN) == ([], 1)


def test_verbose_restores_the_original_output(tmp_path):
    """`say()` is off by default and on when asked -- the output is not lost.

    That is what lets a caller keep the builder's console output byte for
    byte while the library stays quiet by default.
    """
    out = _run("import asteroid_catalog as ac; ac.set_verbose(True); "
               "ac.say('hello')", tmp_path)
    assert out.stdout.strip() == "hello"
    out = _run("import asteroid_catalog as ac; ac.say('hello')", tmp_path)
    assert out.stdout == ""


def test_output_directory_is_relative_and_env_overridable(tmp_path):
    """An absolute default is wrong on every machine but the author's."""
    out = _run("import asteroid_catalog as ac; print(ac.CONFIG.output_dir)",
               tmp_path)
    assert out.returncode == 0, out.stderr
    assert os.path.realpath(out.stdout.strip()) == \
        os.path.realpath(os.path.join(str(tmp_path), "asteroid_catalog_data"))


def test_printed_output_is_ascii():
    """Windows picks cp1252 for a redirected stdout.

    One non-ASCII character in a printed string kills
    `asteroid-catalog build > run.log` with a UnicodeEncodeError before a row
    is written -- and it never fires in a console, so it is invisible until
    somebody logs a long run, which is when it costs most.

    COMMENTS, DOCSTRINGS AND THE `notes` FIELDS KEEP THEIR UNICODE.  Those are
    prose and data, not output, so only the arguments of a `say`/`print`/`warn`
    call are checked.
    """
    pkg = os.path.join(REPO, "asteroid_catalog")
    files = [os.path.join(pkg, f) for f in sorted(os.listdir(pkg)) if f.endswith(".py")]
    bad, n = source.printed_non_ascii(REPO, files, callers=("say", "print", "warn"))
    assert n > 0
    assert not bad, "non-ASCII in printed strings:\n  " + "\n  ".join(bad)
