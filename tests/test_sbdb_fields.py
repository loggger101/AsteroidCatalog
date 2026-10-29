# -*- coding: utf-8 -*-
"""The SBDB field-discovery check: what SBDB offers against what the build asks.

Synthetic `?info=field` answers only; the network is refused by conftest, and
`--from` is the path the tool takes without it.
"""

import json

from _support import load_tool

from asteroid_catalog.jpl import _JPL_FIELDS, _JPL_SAFE_FIELDS

fields = load_tool("sbdb_fields")


def _payload(names):
    """An `?info=field` answer in SBDB's shape, split over two blocks."""
    names = list(names)
    half = len(names) // 2
    return {"signature": {"version": "1.0"},
            "info": {"field": {
                "object": {"field_label": "Object Fields",
                           "list": [{"name": n, "description": n + " desc"} for n in names[:half]]},
                "orbit": {"field_label": "Orbit Fields",
                          "list": [{"name": n, "description": n + " desc"} for n in names[half:]]},
            }}}


def test_offered_fields_reads_every_block():
    got = fields.offered_fields(_payload(["pdes", "a", "e", "sigma_a"]))
    assert got == {"pdes": "pdes desc", "a": "a desc", "e": "e desc", "sigma_a": "sigma_a desc"}


def test_compare_sorts_each_field_into_its_answer():
    r = fields.compare(["pdes", "a", "G", "sigma_a"],
                       requested=["pdes", "a", "soln_date", "gone"],
                       declined={"G": "rare", "old": "left the list"},
                       unlisted_ok={"soln_date": "answers"})
    assert r["requested"] == ["pdes", "a"]
    assert r["declined"] == ["G"]
    assert r["stale_declines"] == ["old"]
    assert r["unreviewed"] == ["sigma_a"]
    assert r["unlisted_ok"] == ["soln_date"]
    assert r["missing"] == ["gone"]


def test_shipped_lists_do_not_contradict_the_fetch():
    assert not set(fields.DECLINED) & set(_JPL_FIELDS)
    assert set(fields.UNLISTED_BUT_ACCEPTED) <= set(_JPL_FIELDS)


def _run(tmp_path, names):
    path = tmp_path / "fields.json"
    path.write_text(json.dumps(_payload(names)), encoding="utf-8")
    return fields.main(["--from", str(path)])


def test_every_requested_field_listed_passes(tmp_path, capsys):
    offered = [f for f in _JPL_FIELDS if f not in fields.UNLISTED_BUT_ACCEPTED]
    assert _run(tmp_path, offered + ["sigma_a"]) == 0
    out = capsys.readouterr().out
    assert "sigma_a" in out           # unreviewed fields are listed, not failed
    assert "not re-asked offline" in out


def test_a_requested_field_sbdb_dropped_fails(tmp_path, capsys):
    # The planted defect: SBDB stops listing `epoch`, which the safe fallback
    # also requests, so a real build would lose JPL entirely.
    assert "epoch" in _JPL_SAFE_FIELDS
    offered = [f for f in _JPL_FIELDS
               if f not in fields.UNLISTED_BUT_ACCEPTED and f != "epoch"]
    assert _run(tmp_path, offered) == 1
    assert "requested but not offered: epoch" in capsys.readouterr().out


def test_a_field_both_declined_and_requested_fails(tmp_path, monkeypatch):
    monkeypatch.setitem(fields.DECLINED, "epoch", "planted")
    offered = [f for f in _JPL_FIELDS if f not in fields.UNLISTED_BUT_ACCEPTED]
    assert _run(tmp_path, offered) == 1
