# -*- coding: utf-8 -*-
"""The CLI survives a cp1252 stdout, because it prints DATA.

THE BUG THIS REPRODUCES WAS FOUND BY RUNNING THE COMMAND, NOT BY A TEST.
`test_library_hygiene.test_printed_output_is_ascii` checks that every string
LITERAL inside a `say`/`print`/`warn` call is ASCII, which is the right rule
for the library: `say()` must be safe under any encoding.

It says nothing about the data flowing THROUGH those calls. The taxonomy
`notes` fields carry real Unicode -- U+2248 in "~3.8-3.9 g/cm3" -- so
`asteroid-catalog taxonomy M` raised UnicodeEncodeError on Windows while the
ASCII test passed. A check that covers the literals is a check on the
literals.

Windows picks cp1252 for a REDIRECTED stdout specifically, so this never fires
in an interactive console: it is invisible until somebody logs a run, which is
when it costs most.
"""

import subprocess
import sys

import pytest

from _support import REPO, repo_env


def _run_under(encoding, *args):
    """Run the CLI with a hostile stdout encoding and no UTF-8 mode."""
    env = repo_env(PYTHONUTF8="0", PYTHONIOENCODING=encoding)
    return subprocess.run([sys.executable, "-m", "asteroid_catalog", *args],
                          capture_output=True, env=env, cwd=REPO)


@pytest.mark.parametrize("args", [
    ("taxonomy", "M"),          # the row whose notes carry U+2248
    ("taxonomy",),              # all of them
    ("--version",),
])
def test_cli_survives_a_cp1252_stdout(args):
    out = _run_under("cp1252", *args)
    assert out.returncode == 0, (
        "the CLI died under cp1252:\n%s" % out.stderr.decode("utf-8", "replace"))
    assert b"UnicodeEncodeError" not in out.stderr


def test_the_data_really_does_carry_non_ascii():
    """Otherwise the test above passes for the wrong reason, forever.

    If the notes were quietly ASCII-fied one day, these tests would go green
    on a package that no longer exercises the case they exist for.
    """
    import asteroid_catalog as ac

    blob = "".join(str(e.get("notes", "")) + str(e.get("composition", ""))
                   for e in ac.TAXONOMY_COMPOSITION.values())
    assert any(ord(ch) > 127 for ch in blob), \
        "no non-ASCII left in the taxonomy data; this test no longer tests it"
