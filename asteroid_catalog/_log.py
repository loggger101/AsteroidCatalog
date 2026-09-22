# -*- coding: utf-8 -*-
"""Output shim, so importing a library never writes to stdout.

`modules/catalog.py` printed a progress line at every fetch, every merge and
every validation step, which is right for a notebook module that is also the
program, and wrong for a package somebody imports to read one taxonomy row.
All 114 of those calls became `say()`.

`say()` is silent by default.  `set_verbose(True)`, or the `--verbose` flag on
the CLI, restores the original console output verbatim.  That is what the
economicspace adapter does, which is why Stage 1's console output there is
unchanged by the split.

WARNINGS ARE NOT PROGRESS AND DO NOT GO THROUGH HERE.  A source that fetched
rows and matched none is a defect in that fetcher, and the whole value of that
message is that it is loud; routing it through a verbosity flag would make the
quiet case the default, which is how NEOWISE contributed zero rows for four
releases while the fetch summary said 183,408.  Those calls use `warn()`,
which always prints.

WRITE ASCII.  Windows picks cp1252 for a redirected stdout, so a single
non-ASCII character in a printed string kills `asteroid-catalog build > run.log`
with a UnicodeEncodeError before a row is written.  Comments, docstrings and
the `notes` fields of the taxonomy rows keep their Unicode; those are data and
prose, not output.
"""

import sys

_VERBOSE = False


def set_verbose(on: bool = True) -> None:
    """Turn the progress output on or off.  Off is the default."""
    global _VERBOSE
    _VERBOSE = bool(on)


def is_verbose() -> bool:
    """Is progress output currently on?"""
    return _VERBOSE


def say(*args, **kwargs) -> None:
    """`print`, but only when verbose.  The signature is print's."""
    if _VERBOSE:
        print(*args, **kwargs)


def warn(*args, **kwargs) -> None:
    """`print`, always, for things a silent run still must not swallow.

    THE RULE FOR CHOOSING BETWEEN THIS AND `say`, because a blanket answer is
    wrong in both directions:

        warn()   a DEFECT IN THIS CODE, or a fatal abort.  A supplement that
                 fetched rows and matched none of them; a schema whose merge
                 key has been renamed upstream; the backbone failing outright.
        say()    an EXTERNAL condition the design tolerates.  MP3C unreachable,
                 a TAP timeout, a retried HTTP error.  These are expected, they
                 are already retried, and printing them unconditionally would
                 make the common case noisy enough that nobody reads either.

    Getting this backwards is not hypothetical.  The zero-match alert is the
    one diagnostic that would have caught a fetcher contributing nothing for
    four releases while its fetch count read 183,408, and a mechanical
    print->say pass silenced it.

    IT WRITES TO STDOUT, NOT STDERR, AND THAT IS DELIBERATE.  The original
    printed these to stdout; moving them would change which stream a consumer's
    log captures, and a message that vanishes from a log is the failure this
    function exists to prevent.  Only the verbosity gate is removed.
    """
    kwargs.setdefault("file", sys.stdout)
    print(*args, **kwargs)
