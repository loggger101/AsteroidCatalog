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

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(code, cwd):
    """Import in a CLEAN interpreter.

    It has to be a subprocess: by the time a test runs, pytest has already
    imported the package, so an in-process check would be asking whether an
    import that already happened is about to print.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
    env.pop("ASTEROID_CATALOG_OUTPUT_DIR", None)
    return subprocess.run([sys.executable, "-c", code], cwd=str(cwd),
                          capture_output=True, text=True, env=env)


def test_import_prints_nothing(tmp_path):
    out = _run("import asteroid_catalog", tmp_path)
    assert out.returncode == 0, out.stderr
    assert out.stdout == "", "import wrote to stdout:\n%s" % out.stdout
    assert out.stderr == "", "import wrote to stderr:\n%s" % out.stderr


def test_import_creates_no_directory(tmp_path):
    """The original made the output dir AND the download cache dir at import.

    Either is a library with a side effect; the cache one is worse, because it
    lands in the system temp directory of a machine that only wanted a
    constant.
    """
    before = set(os.listdir(tmp_path))
    out = _run("import asteroid_catalog as ac; ac.CONFIG.output_dir", tmp_path)
    assert out.returncode == 0, out.stderr
    assert set(os.listdir(tmp_path)) == before, \
        "import created %s" % (set(os.listdir(tmp_path)) - before)


def test_verbose_restores_the_original_output(tmp_path):
    """`say()` is off by default and on when asked -- the output is not lost.

    That is what lets the economicspace adapter keep Stage 1's console output
    byte for byte while the library stays quiet.
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
    import ast
    import io

    bad = []
    pkg = os.path.join(REPO, "asteroid_catalog")
    for fname in sorted(os.listdir(pkg)):
        if not fname.endswith(".py"):
            continue
        path = os.path.join(pkg, fname)
        src = io.open(path, encoding="utf-8").read()
        for node in ast.walk(ast.parse(src)):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("say", "print", "warn")):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    nonascii = [ch for ch in sub.value if ord(ch) > 127]
                    if nonascii:
                        bad.append("%s:%d %r" % (fname, sub.lineno,
                                                 "".join(sorted(set(nonascii)))))
    assert not bad, "non-ASCII in printed strings:\n  " + "\n  ".join(bad)
