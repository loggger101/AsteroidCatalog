# -*- coding: utf-8 -*-
"""The build's file handling and the CLI's edges, without a network.

Every fetcher is replaced with a stub, so `build_catalog` runs end to end on
three synthetic bodies in milliseconds.
"""

import pandas as pd
import pytest

import asteroid_catalog as ac
import asteroid_catalog.build as build
from asteroid_catalog.cli import main


@pytest.fixture
def offline(monkeypatch):
    """A build whose only source is three JPL rows, and no MPC download."""
    jpl = pd.DataFrame({"designation": ["1", "2", "3"],
                        "diameter_km": [939.4, 512.0, 250.0],
                        "absolute_magnitude_h": [3.3, 4.1, 5.0],
                        "semi_major_axis_au": [2.77, 2.77, 2.36],
                        "source_jpl": True})
    monkeypatch.setattr(build, "fetch_jpl_sbdb", lambda config: jpl.copy())
    for name in ("fetch_ssodnet", "fetch_neowise", "fetch_mp3c"):
        monkeypatch.setattr(build, name, lambda config: pd.DataFrame())
    monkeypatch.setattr(build, "fetch_mpc_identifications", lambda config: {})


def test_a_library_build_creates_its_output_directory(offline, tmp_path):
    """Only the CLI used to make it, so `build_catalog()` from Python fetched
    everything and then died writing the CSV into a directory that was not
    there."""
    out = tmp_path / "not" / "yet"
    df = ac.build_catalog(ac.CatalogConfig(output_dir=str(out)))
    assert len(df) == 3
    assert (out / "asteroid_catalog.csv").exists()


def test_a_failed_build_creates_nothing(monkeypatch, tmp_path):
    for name in ("fetch_jpl_sbdb", "fetch_ssodnet", "fetch_neowise", "fetch_mp3c"):
        monkeypatch.setattr(build, name, lambda config: pd.DataFrame())
    out = tmp_path / "never"
    assert main(["build", "--out", str(out), "--quiet"]) == 1
    assert not out.exists()


def test_the_output_dir_default_is_read_when_the_config_is_made(monkeypatch):
    """Not when the package was imported: a notebook sets the variable after."""
    monkeypatch.setenv("ASTEROID_CATALOG_OUTPUT_DIR", "/somewhere/else")
    assert ac.CatalogConfig().output_dir == "/somewhere/else"


@pytest.mark.parametrize("given,shown", [("M", "M"), ("m", "M"), ("sq", "Sq"),
                                         ("Sq2", "S")])
def test_taxonomy_resolves_a_class_as_the_pipeline_does(capsys, given, shown):
    assert main(["taxonomy", given]) == 0
    out = capsys.readouterr().out
    group = ac.TAXONOMY_COMPOSITION[shown]["group"]
    assert "group                %s" % group in out


def test_taxonomy_refuses_what_it_cannot_resolve(capsys):
    assert main(["taxonomy", "!"]) == 1
    assert "unknown class" in capsys.readouterr().err


def test_a_negative_row_cap_is_refused(offline, tmp_path):
    # Offline, so that if the check ever goes, this fails on its exit code
    # rather than starting a real build.
    with pytest.raises(SystemExit) as exc:
        main(["build", "--jpl-limit", "-5", "--out", str(tmp_path), "--quiet"])
    assert exc.value.code == 2          # argparse's usage error, before any fetch


@pytest.mark.parametrize("previous", ["{broken", None])
def test_package_reports_a_bad_previous_manifest(tmp_path, capsys, previous):
    path = tmp_path / "manifest.json"
    if previous is not None:
        path.write_text(previous, encoding="utf-8")
    rc = main(["package", str(tmp_path), "--out", str(tmp_path / "dist"),
               "--tag", "t", "--previous", str(path)])
    assert rc == 1
    assert capsys.readouterr().err.startswith("FAIL")


def test_lookup_prints_a_bounded_number_of_rows(tmp_path, capsys):
    """A substring search: "1" is in most numbered designations."""
    csv = tmp_path / "catalog.csv"
    pd.DataFrame({"designation": [str(i) for i in range(1, 121)]}).to_csv(csv, index=False)
    # "1" appears in 40 of the designations 1..120.
    assert main(["lookup", "1", "--catalog", str(csv), "--max-rows", "5"]) == 0
    assert "5 of 40 matches shown" in capsys.readouterr().out
    assert main(["lookup", "1", "--catalog", str(csv), "--max-rows", "0"]) == 0
    assert "matches shown" not in capsys.readouterr().out
    assert main(["lookup", "  ", "--catalog", str(csv)]) == 1     # blank: no match


def test_the_manifest_counts_measured_diameters_without_the_column():
    from asteroid_catalog.release import measured_diameters
    assert measured_diameters(pd.DataFrame({"designation": ["1"]})) == 0
    assert measured_diameters(pd.DataFrame(
        {"diameter_source": ["measured", "derived_h_orbit_albedo"]})) == 1
