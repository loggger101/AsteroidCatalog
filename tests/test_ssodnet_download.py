# -*- coding: utf-8 -*-
"""The ~500 MB ssoBFT download survives a bad minute on its host.

The first data-2026-09-25 publish run lost SsODNet to one timeout, 135 s in,
and the release gate refused the build.  No network here: `requests.get` is
replaced with a fake that fails as the host did.
"""

import pytest
import requests

from asteroid_catalog import CONFIG
from asteroid_catalog import ssodnet


class _Resp:
    headers = {"content-length": "6"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield b"PAR1ok"


def _fake_get(failures):
    calls = {"n": 0}

    def get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= len(failures):
            raise failures[calls["n"] - 1]
        return _Resp()
    return get, calls


@pytest.fixture(autouse=True)
def _no_waiting(monkeypatch):
    monkeypatch.setattr(ssodnet._time, "sleep", lambda s: None)


def test_a_timeout_is_retried(tmp_path, monkeypatch):
    get, calls = _fake_get([requests.exceptions.Timeout(),
                            requests.exceptions.ConnectionError("reset")])
    monkeypatch.setattr(ssodnet.requests, "get", get)
    dest = str(tmp_path / "ssoBFT.parquet")
    assert ssodnet._download_ssodnet_parquet(dest, CONFIG)
    assert calls["n"] == 3
    assert open(dest, "rb").read() == b"PAR1ok"


def test_it_gives_up_after_the_last_attempt(tmp_path, monkeypatch):
    get, calls = _fake_get([requests.exceptions.Timeout()] * 5)
    monkeypatch.setattr(ssodnet.requests, "get", get)
    dest = str(tmp_path / "ssoBFT.parquet")
    assert not ssodnet._download_ssodnet_parquet(dest, CONFIG)
    assert calls["n"] == ssodnet._SSODNET_DOWNLOAD_ATTEMPTS
    assert not (tmp_path / "ssoBFT.parquet.part").exists()


def test_a_404_is_not_retried(tmp_path, monkeypatch):
    resp = requests.Response()
    resp.status_code = 404
    get, calls = _fake_get([requests.exceptions.HTTPError(response=resp)] * 5)
    monkeypatch.setattr(ssodnet.requests, "get", get)
    assert not ssodnet._download_ssodnet_parquet(str(tmp_path / "x.parquet"), CONFIG)
    assert calls["n"] == 1, "a missing file will be missing on the next try too"
