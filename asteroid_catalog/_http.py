# -*- coding: utf-8 -*-
"""Streaming a response with a byte-progress bar, written once.

JPL, NEOWISE, SsODNet and the MPC file each carried their own copy of this
loop -- read `content-length`, open a tqdm bar, walk `iter_content` -- and the
copies had drifted apart in nothing but chunk size and refresh interval.  The
fetchers still own their requests and their error handling; only the transfer
lives here.

Only `resp.headers` and `resp.iter_content(chunk_size=...)` are used, which is
the whole surface the download tests fake.
"""

import os
import time

from tqdm.auto import tqdm


def _progress(resp, desc: str, mininterval: float) -> tqdm:
    """A byte bar: a percentage when the server sends Content-Length, else an
    indeterminate bar that still counts bytes as they arrive."""
    total = int(resp.headers.get("content-length") or 0) or None
    return tqdm(total=total, desc=desc, unit="B", unit_scale=True,
                unit_divisor=1024, leave=True, mininterval=mininterval)


def read_body(resp, desc: str, chunk_size: int = 1 << 16,
              mininterval: float = 0.3) -> bytes:
    """The whole body of a streamed response, held in memory."""
    chunks = []
    with _progress(resp, desc, mininterval) as pbar:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if chunk:
                chunks.append(chunk)
                pbar.update(len(chunk))
    return b"".join(chunks)


def write_body(resp, dest: str, desc: str, chunk_size: int = 1 << 20,
               mininterval: float = 0.5) -> None:
    """Stream a response to `dest` atomically, through `dest + ".part"`.

    On any failure the `.part` file is removed and the exception propagates,
    so a retry never finds a half-written file where a cache check looks.
    """
    tmp = dest + ".part"
    try:
        with open(tmp, "wb") as fh, _progress(resp, desc, mininterval) as pbar:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    fh.write(chunk)
                    pbar.update(len(chunk))
        _replace(tmp, dest)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _replace(tmp: str, dest: str) -> None:
    """`os.replace`, retried: Windows can briefly hold a freshly-closed file
    open through the indexer or antivirus."""
    for _ in range(8):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError:
            time.sleep(0.5)
    os.replace(tmp, dest)  # final attempt; raises if still locked
