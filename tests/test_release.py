# -*- coding: utf-8 -*-
"""The release packager: its gates refuse, and its assets are what they claim.

Synthetic builds only, like the rest of the suite.  The real floors are sized
for a 1.5 M-row catalog, so these tests pass their own.
"""

import gzip
import hashlib
import json
import os

import pandas as pd
import pytest

from asteroid_catalog import CONFIG
from asteroid_catalog.cli import main
from asteroid_catalog.release import (
    CATALOG_GZ, CATALOG_PARQUET, MANIFEST, NOTES, REJECTED_CSV, TAXONOMY_JSON,
    check_release, gzip_deterministic, package_release, source_counts,
)

ALL4 = "JPL SBDB;SsODNet;NEOWISE;MP3C"
FLOORS = {"rows": 4, "measured_diameters": 1, "JPL SBDB": 4, "SsODNet": 2,
          "NEOWISE": 1, "MP3C": 2}


def _catalog(n=6, sources=None):
    return pd.DataFrame({
        # "1" .. "5" look like integers; the reader must keep them strings.
        "designation": [str(i + 1) for i in range(n - 1)] + ["2026 AB1"],
        "diameter_km": [10.0 + i for i in range(n)],
        "diameter_source": ["measured"] * 2 + ["derived: H + class albedo"] * (n - 2),
        "derived_diameter_is_estimate": [False] * 2 + [True] * (n - 2),
        "diameter_sources_agree": [True, False] + [None] * (n - 2),
        "sources": sources or [ALL4] * 2 + ["JPL SBDB;SsODNet;MP3C"] * (n - 2),
        "catalog_date": ["2026-09-23"] * n,
        "pipeline_version": [CONFIG.pipeline_version] * n,
    })


def _write_build(tmp_path, df):
    build = tmp_path / "build"
    build.mkdir()
    df.to_csv(build / "asteroid_catalog.csv", index=False, lineterminator="\r\n")
    pd.DataFrame({"designation": ["x"], "reason": ["no orbit"]}).to_csv(
        build / REJECTED_CSV, index=False, lineterminator="\r\n")
    return build


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_good_build_passes():
    assert check_release(_catalog(), floors=FLOORS) == []


def test_source_counts_read_the_sources_column():
    assert source_counts(_catalog()) == {
        "JPL SBDB": 6, "SsODNet": 6, "NEOWISE": 2, "MP3C": 6}


def test_a_source_that_contributed_nothing_is_refused():
    df = _catalog(sources=["JPL SBDB;SsODNet;NEOWISE"] * 6)
    problems = check_release(df, floors=FLOORS)
    assert len(problems) == 1 and problems[0].startswith("MP3C: 0 bodies")


def test_every_failed_gate_is_reported():
    df = _catalog()
    df.loc[1, "designation"] = "1"
    df.loc[2, "pipeline_version"] = "0.0.1"
    problems = check_release(df, floors=FLOORS)
    assert any("duplicated" in p for p in problems)
    assert any(p.startswith("pipeline_version: expected one value") for p in problems)
    assert any("this package writes" in p for p in problems)


def test_a_catalog_that_shrank_is_refused_unless_allowed():
    previous = {"release_tag": "data-2026-09-01", "rows": 7,
                "sources": {"JPL SBDB": 7, "NEOWISE": 2}}
    problems = check_release(_catalog(), previous=previous, floors=FLOORS)
    assert problems == ["rows: 6, down from 7 in data-2026-09-01 (more than 0.5%)",
                        "JPL SBDB: 6 bodies, down from 7 in data-2026-09-01 "
                        "(more than 2%)"]
    assert check_release(_catalog(), previous=previous, floors=FLOORS,
                         allow_shrink=True) == []


def test_the_gzip_is_deterministic(tmp_path):
    src = tmp_path / "a.csv"
    src.write_bytes(b"designation\r\n1\r\n")
    gzip_deterministic(str(src), str(tmp_path / "1.gz"))
    os.utime(src, (0, 12345))
    gzip_deterministic(str(src), str(tmp_path / "2.gz"))
    assert (tmp_path / "1.gz").read_bytes() == (tmp_path / "2.gz").read_bytes()


def test_package_writes_what_the_manifest_says(tmp_path):
    build = _write_build(tmp_path, _catalog())
    out = tmp_path / "dist"
    m = package_release(str(build), str(out), "data-2026-09-23",
                        source_commit="abc123", floors=FLOORS)

    assert json.loads((out / MANIFEST).read_text(encoding="utf-8")) == m
    assert (out / NOTES).exists()
    assert set(m["files"]) == {CATALOG_GZ, CATALOG_PARQUET, REJECTED_CSV,
                               TAXONOMY_JSON}
    for name, entry in m["files"].items():
        assert entry["sha256"] == _sha(out / name)
        assert entry["bytes"] == os.path.getsize(out / name)

    # The CSV inside the gzip is the build's file, byte for byte, CRLF and all.
    raw = gzip.decompress((out / CATALOG_GZ).read_bytes())
    assert raw == (build / "asteroid_catalog.csv").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == m["catalog_csv"]["sha256"]

    assert m["rows"] == 6 and m["rejected_rows"] == 1
    assert m["measured_diameters"] == 2
    assert m["pipeline_version"] == CONFIG.pipeline_version
    assert m["catalog_date"] == "2026-09-23"


def test_the_taxonomy_ships_exactly(tmp_path):
    import asteroid_catalog as ac
    build = _write_build(tmp_path, _catalog())
    package_release(str(build), str(tmp_path / "dist"), "t", floors=FLOORS)
    shipped = json.loads((tmp_path / "dist" / TAXONOMY_JSON).read_text(encoding="utf-8"))
    assert shipped["TAXONOMY_COMPOSITION"] == ac.TAXONOMY_COMPOSITION
    assert shipped["PGM_ENRICHMENT_BY_TYPE"] == ac.PGM_ENRICHMENT_BY_TYPE
    from asteroid_catalog.physics import DENSITY_LIMITS_GCM3
    assert {k: tuple(v) for k, v in shipped["DENSITY_LIMITS_GCM3"].items()} \
        == DENSITY_LIMITS_GCM3


def test_the_parquet_keeps_designations_as_strings(tmp_path):
    build = _write_build(tmp_path, _catalog())
    package_release(str(build), str(tmp_path / "dist"), "t", floors=FLOORS)
    pq = pd.read_parquet(tmp_path / "dist" / CATALOG_PARQUET)
    assert pq["designation"].tolist() == ["1", "2", "3", "4", "5", "2026 AB1"]
    assert pd.api.types.is_bool_dtype(pq["derived_diameter_is_estimate"])
    # True/False/blank reads as object; it must come back boolean, blanks as NA.
    agree = pq["diameter_sources_agree"]
    assert pd.api.types.is_bool_dtype(agree)
    assert agree.tolist()[:2] == [True, False] and agree.isna().sum() == 4
    assert len(pq.columns) == 8


def test_a_refused_build_writes_nothing(tmp_path):
    build = _write_build(tmp_path, _catalog(sources=["JPL SBDB"] * 6))
    with pytest.raises(ValueError, match="must not be published"):
        package_release(str(build), str(tmp_path / "dist"), "t", floors=FLOORS)
    assert not (tmp_path / "dist").exists()


def test_the_cli_refuses_with_a_nonzero_exit(tmp_path, capsys):
    # The real floors: a six-row catalog is far below every one of them.
    build = _write_build(tmp_path, _catalog())
    rc = main(["package", str(build), "--out", str(tmp_path / "dist"),
               "--tag", "t"])
    assert rc == 1
    assert "below the floor" in capsys.readouterr().err


def test_data_version_matches_the_config():
    """The stamp a manifest carries is the one stamped into the rows.

    Moved here from the retired consumer-contract suite: it is a property of
    what a release PUBLISHES, which is the only surface a consumer reads now.
    """
    import asteroid_catalog as ac
    assert ac.DATA_VERSION == ac.CONFIG.pipeline_version
