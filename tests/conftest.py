# -*- coding: utf-8 -*-
"""The suite never touches the network, and this makes that a fact.

CI's workflow promises it, and a promise nothing checks holds until the day a
test starts a real build by accident: one did, while this file did not exist,
and began the 850 MB SsODNet download.  Every socket connection now raises, so
such a test fails in milliseconds instead.  Tests that run the CLI in a
subprocess are not covered, and do not need the network either.
"""

import socket

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(self, address, *args, **kwargs):
        raise OSError("test tried to connect to %r; the suite must not touch "
                      "the network" % (address,))
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
