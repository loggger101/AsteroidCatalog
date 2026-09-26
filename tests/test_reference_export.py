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

import os

import pytest

import asteroid_catalog as ac
from _support import REPO, load_tool

REFERENCE = os.path.join(REPO, "reference")
exporter = load_tool("export_reference")


@pytest.mark.parametrize("name", exporter.FILES)
def test_committed_export_is_current(name, tmp_path):
    committed = os.path.join(REFERENCE, name)
    assert os.path.exists(committed), (
        "%s is not committed; run `py tools/export_reference.py`" % name)

    # Render into a scratch directory, then compare.  Running the exporter
    # into reference/ would overwrite the thing under test, which is a check
    # that cannot fail.
    exporter.export(str(tmp_path))
    fresh = (tmp_path / name).read_bytes()
    with open(committed, "rb") as fh:
        have = fh.read()
    assert fresh == have, (
        "%s is stale -- the table changed and the export did not. "
        "Run `py tools/export_reference.py` and commit the result." % name)


def test_export_covers_every_class():
    """A rendering that silently drops rows is worse than no rendering."""
    with open(os.path.join(REFERENCE, "taxonomy_composition.csv"),
              encoding="utf-8") as fh:
        rows = fh.read().splitlines()
    assert len(rows) - 1 == len(ac.TAXONOMY_COMPOSITION)
