# -*- coding: utf-8 -*-
"""The committed CSVs still match the tables they were rendered from.

TWO COPIES OF ONE TABLE IS THE DEFECT, and the fix is not "remember to
re-export".  A note asking the next reader to keep two things in step is a
promise a human keeps, so it holds until the day somebody does not, and
nothing goes red in between.

So the export is regenerated here, in a temp directory, and held byte for byte
against what is committed.  Edit a taxonomy row without re-exporting and the
suite says so.
"""

import io
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFERENCE = os.path.join(REPO, "reference")
FILES = ["taxonomy_composition.csv", "pgm_enrichment.csv"]


@pytest.mark.parametrize("name", FILES)
def test_committed_export_is_current(name, tmp_path):
    committed = os.path.join(REFERENCE, name)
    assert os.path.exists(committed), (
        "%s is not committed; run `py tools/export_reference.py`" % name)

    env = dict(os.environ)
    env["PYTHONPATH"] = REPO + os.pathsep + env.get("PYTHONPATH", "")
    # Render into a scratch tree, then compare. Running the real exporter
    # would overwrite the thing under test, which is a check that cannot fail.
    scratch = tmp_path / "reference"
    scratch.mkdir()
    code = (
        "import sys, os;"
        "sys.path.insert(0, %r);"
        "sys.argv=['x'];"
        "import tools.export_reference as e;"
        "e.write(os.path.join(%r, 'taxonomy_composition.csv'), e.FIELDS, e.taxonomy_rows());"
        "e.write(os.path.join(%r, 'pgm_enrichment.csv'), ['spectral_type','pgm_enrichment'],"
        " sorted(e.PGM_ENRICHMENT_BY_TYPE.items()))"
        % (REPO, str(scratch), str(scratch))
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, env=env, cwd=REPO)
    assert out.returncode == 0, out.stderr

    fresh = io.open(str(scratch / name), "rb").read()
    have = io.open(committed, "rb").read()
    assert fresh == have, (
        "%s is stale -- the table changed and the export did not. "
        "Run `py tools/export_reference.py` and commit the result." % name)


def test_export_covers_every_class():
    """A rendering that silently drops rows is worse than no rendering."""
    import asteroid_catalog as ac

    rows = io.open(os.path.join(REFERENCE, "taxonomy_composition.csv"),
                   encoding="utf-8").read().splitlines()
    assert len(rows) - 1 == len(ac.TAXONOMY_COMPOSITION)
