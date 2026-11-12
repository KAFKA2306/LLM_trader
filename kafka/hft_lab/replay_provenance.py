"""Provenance-bound, offline L2 replay. No exchange calls or orders.

A manifest is a caller declaration, not independent proof of source authenticity.
"""
import hashlib
import json
from collections.abc import Mapping

from book_replay import BookEvidenceError, DiffDepthBook


def _identity(value, name):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise BookEvidenceError(f"{name} must be a nonempty exact string")
    return value


def _sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("utf-8")).hexdigest()


class ProvenanceReplay:
    """Rejects mixed venue/symbol/source and uncommitted input before state changes."""

    def __init__(self, manifest, snapshot, events):
        if not isinstance(manifest, Mapping):
            raise BookEvidenceError("manifest must be a mapping")
        self.venue = _identity(manifest.get("venue"), "venue")
        self.symbol = _identity(manifest.get("symbol"), "symbol")
        self.source = _identity(manifest.get("source"), "source")
        if manifest.get("schema") != "l2-diff-v1":
            raise BookEvidenceError("unsupported manifest schema")
        if not isinstance(events, list):
            raise BookEvidenceError("events must be a list")
        if not isinstance(snapshot, Mapping):
            raise BookEvidenceError("snapshot must be a mapping")
        if manifest.get("snapshot_sha256") != _sha256(snapshot):
            raise BookEvidenceError("snapshot hash mismatch")
        if manifest.get("events_sha256") != _sha256(events):
            raise BookEvidenceError("events hash mismatch")
        self.book = DiffDepthBook(snapshot)
        self._events = events
        self.__events_hash = manifest["events_sha256"]
        self._cursor = 0

    def step(self):
        if self._cursor >= len(self._events):
            return False
        event = self._events[self._cursor]
        if not isinstance(event, Mapping):
            raise BookEvidenceError("event must be a mapping")
        if event.get("venue") != self.venue or event.get("symbol") != self.symbol:
            raise BookEvidenceError("mixed venue/symbol: event rejected")
        # Check the entire event against the frozen hash before applying any update.
        if _sha256(self._events) != self._expected_events_hash:
            raise BookEvidenceError("event input mutated after validation")
        applied = self.book.apply(event)
        self._cursor += 1
        return applied

    @property
    def _expected_events_hash(self):
        return self.__events_hash

    def top(self):
        return self.book.top()


def make_manifest(venue, symbol, source, snapshot, events):
    """Create a local manifest; this does not validate external data rights."""
    return {"schema": "l2-diff-v1", "venue": _identity(venue, "venue"),
            "symbol": _identity(symbol, "symbol"), "source": _identity(source, "source"),
            "snapshot_sha256": _sha256(snapshot), "events_sha256": _sha256(events)}
