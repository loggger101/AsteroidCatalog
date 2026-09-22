# -*- coding: utf-8 -*-
"""A defect must be audible in a silent run.

WHY THIS FILE EXISTS.  The package was extracted by a mechanical pass that
turned all 114 `print` calls into `say`, which is silent unless the caller asks
for progress output.  That was right for 104 of them and WRONG for the ten
here, and the worst of the ten is the zero-match alert: the one diagnostic that
would have caught a fetcher contributing nothing for four releases while its
own fetch summary reported 183,408 rows.

A diagnostic that has gone quiet reads exactly like a clean result, so nothing
about the silenced version looked wrong.  These tests are what makes the split
between `say` and `warn` a decision rather than an accident.
"""

import contextlib
import io

import pandas as pd
import pytest

import asteroid_catalog as ac
from asteroid_catalog import _log


@pytest.fixture(autouse=True)
def quiet():
    """Every test here runs with progress output OFF -- the default."""
    before = _log.is_verbose()
    _log.set_verbose(False)
    yield
    _log.set_verbose(before)


def _capture(fn, *a, **kw):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def test_zero_match_alert_is_audible_when_quiet():
    """A supplement that matches NOTHING is a bug in that fetcher.

    Never an empty upstream table: the rows are there, the key is wrong.  The
    float-typed identifier that stringifies to "3.0" is the classic cause.
    """
    backbone = pd.DataFrame({"designation": ["1", "2", "3"],
                             "semi_major_axis_au": [2.7, 2.8, 2.9]})
    # designations that exist nowhere in the backbone: every row enters as a
    # new body with no orbital elements, and validation will drop them all.
    supplement = pd.DataFrame({"designation": ["9001", "9002"],
                               "albedo": [0.1, 0.2]})
    _, out = _capture(ac.merge_sources,
                      {"Backbone": backbone, "Broken": supplement})
    assert "ZERO" in out.upper(), (
        "the zero-match alert did not print in a quiet run; it is the one "
        "diagnostic that catches a silently-broken merge key\n%s" % out)
    assert "Broken" in out, "the alert must name the source"


def test_routine_progress_stays_quiet():
    """The other side of the same decision.

    If everything were loud, the common case would be noisy enough that nobody
    reads either, which is the same failure by a different route.
    """
    backbone = pd.DataFrame({"designation": ["1", "2", "3"],
                             "semi_major_axis_au": [2.7, 2.8, 2.9]})
    good = pd.DataFrame({"designation": ["1", "2"], "albedo": [0.1, 0.2]})
    _, out = _capture(ac.merge_sources, {"Backbone": backbone, "Good": good})
    assert out.strip() == "", "a clean merge should say nothing when quiet:\n%s" % out


def test_missing_designation_column_is_audible():
    """A source with no merge key at all is a fetcher defect, not an outage."""
    backbone = pd.DataFrame({"designation": ["1"], "semi_major_axis_au": [2.7]})
    keyless = pd.DataFrame({"albedo": [0.1]})
    _, out = _capture(ac.merge_sources,
                      {"Backbone": backbone, "Keyless": keyless})
    assert "Keyless" in out and "designation" in out


def test_validate_without_a_key_is_audible():
    _, out = _capture(ac.validate_and_filter,
                      pd.DataFrame({"albedo": [0.1]}), ac.CONFIG)
    assert "designation" in out


def test_warn_goes_to_stdout_not_stderr(capsys):
    """The stream is the original's, deliberately.

    Moving these to stderr would change which stream a consumer's log
    captures, and a message that vanishes from a log is the failure `warn`
    exists to prevent.
    """
    _log.warn("audible")
    cap = capsys.readouterr()
    assert cap.out.strip() == "audible"
    assert cap.err == ""
