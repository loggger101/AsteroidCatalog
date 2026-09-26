# -*- coding: utf-8 -*-
"""The transfers survive the ways a remote service fails.  No network: every
response here is a stand-in that fails the way a real host has."""

import pytest
import requests

from asteroid_catalog import CatalogConfig
from asteroid_catalog import neowise
from asteroid_catalog._http import write_body


class _Stream:
    """A streamed response whose body arrives in chunks, or breaks mid-way."""

    def __init__(self, chunks, fail_after=None):
        self.headers = {"content-length": str(sum(len(c) for c in chunks))}
        self._chunks, self._fail_after = chunks, fail_after

    def iter_content(self, chunk_size):
        for i, chunk in enumerate(self._chunks):
            if i == self._fail_after:
                raise requests.exceptions.ChunkedEncodingError("cut off")
            yield chunk


def test_write_body_replaces_the_file_only_when_complete(tmp_path):
    dest = tmp_path / "cache.bin"
    write_body(_Stream([b"abc", b"def"]), str(dest), "test")
    assert dest.read_bytes() == b"abcdef"
    assert not (tmp_path / "cache.bin.part").exists()


def test_a_broken_transfer_keeps_the_previous_file(tmp_path):
    """What the SsODNet and MPC stale-cache fallbacks rely on."""
    dest = tmp_path / "cache.bin"
    dest.write_bytes(b"previous")
    with pytest.raises(requests.exceptions.ChunkedEncodingError):
        write_body(_Stream([b"abc", b"def"], fail_after=1), str(dest), "test")
    assert dest.read_bytes() == b"previous"
    assert not (tmp_path / "cache.bin.part").exists()


# ── NEOWISE's asynchronous (IVOA UWS) job ───────────────────────────────────
class _Reply:
    def __init__(self, status=200, text="", content=b"", headers=None):
        self.status_code, self.text, self.content = status, text, content
        self.headers = headers or {}


class _UWS:
    """An IRSA async endpoint: submit, run, poll, fetch."""

    def __init__(self, location, run_status=200, phases=("EXECUTING", "COMPLETED")):
        self.location, self.run_status = location, run_status
        self.phases, self.urls, self.closed = list(phases), [], False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    def post(self, url, data=None, **kw):
        self.urls.append(url)
        if data.get("PHASE") == "RUN":
            return _Reply(self.run_status)
        return _Reply(303, headers={"Location": self.location})

    def get(self, url, **kw):
        self.urls.append(url)
        if url.endswith("/phase"):
            return _Reply(text=self.phases.pop(0) if len(self.phases) > 1 else self.phases[0])
        return _Reply(content=b"asteroid_number,prov_desig\n1,\n")


@pytest.fixture
def uws(monkeypatch):
    monkeypatch.setattr(neowise._time, "sleep", lambda s: None)

    def install(**kw):
        fake = _UWS(**kw)
        monkeypatch.setattr(neowise.requests, "Session", lambda: fake)
        return fake
    return install


def test_a_relative_job_url_is_resolved(uws):
    """UWS allows `Location: /TAP/async/<id>`; used raw, every later request
    went to a URL with no host."""
    fake = uws(location="/TAP/async/job42")
    body = neowise._neowise_fetch_async({}, CatalogConfig())
    assert body.startswith(b"asteroid_number")
    assert all(u.startswith("https://irsa.ipac.caltech.edu/TAP/async")
               for u in fake.urls)
    assert fake.closed


def test_a_refused_run_is_given_up_at_once(uws):
    """It used to poll a job that would never start, for the whole ceiling."""
    fake = uws(location="https://irsa.ipac.caltech.edu/TAP/async/j", run_status=500)
    assert neowise._neowise_fetch_async({}, CatalogConfig()) is None
    assert len(fake.urls) == 2          # submit and RUN; no polling


def test_the_wait_ceiling_is_wall_clock(uws, monkeypatch):
    """Only the 2 s sleeps used to count, so slow polls ran far past it."""
    clock = iter(range(0, 10_000, 100))            # every call: 100 s later
    monkeypatch.setattr(neowise._time, "monotonic", lambda: next(clock))
    fake = uws(location="https://irsa.ipac.caltech.edu/TAP/async/j",
               phases=("EXECUTING",))
    config = CatalogConfig(neowise_async_max_wait_s=900)
    assert neowise._neowise_fetch_async({}, config) is None
    polls = sum(u.endswith("/phase") for u in fake.urls) - 1   # minus the RUN
    assert polls <= 9
