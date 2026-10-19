"""P1: the production RTDB adapter for the Publisher. A thin, GUARDED wrapper over the platform's BrainRtdb REST client.

  * refuses to construct unless `armed=True` (nothing in this repository passes it);
  * every update is re-checked against security_model.publisher_key_allowed for the producing Brain before it reaches the transport;
  * maps transport outcomes onto the two failure kinds the LivePublisher reasons about: DEFINITE (HTTP 4xx: nothing applied) and AMBIGUOUS (anything else
    after the request left: it may have been applied, so the caller reads back).
BrainRtdb is built with brain_id=None because its client-side ownership table is the LEGACY specialist table; the Publisher's own guard replaces it.
"""
from __future__ import annotations

import re

from ..rtdb import BrainRtdb, BrainRtdbError
from .model import RtdbAmbiguousFailure, RtdbDefiniteFailure
from .security_model import assert_publisher_keys

_4XX = re.compile(r"->\s*4\d\d\b")


class RtdbRestPublisherClient:
    def __init__(self, url, *, brain_id: str, tokens=None, transport=None, armed: bool = False, **kw):
        if not armed:
            raise PermissionError("RtdbRestPublisherClient refused: not armed (no production Publisher is enabled by this change)")
        self.brain_id = brain_id
        self._db = BrainRtdb(url, tokens=tokens, transport=transport, brain_id=None, **kw)

    def get(self, path):
        return self._db.get(path)

    def update(self, updates):
        assert_publisher_keys(self.brain_id, updates)
        try:
            return self._db.update(updates)
        except BrainRtdbError as e:
            if _4XX.search(str(e)):
                raise RtdbDefiniteFailure(str(e)) from None
            raise RtdbAmbiguousFailure(str(e)) from None
