"""
Telemetry.py
------------

TelemetryKernel: append-only deterministic ledger.

Every component that changes caller state writes here, and nothing ever
rewrites or deletes an entry. The ledger is the audit trail, and it is the
substrate replay equivalence is checked against: two runs over identical
inputs must produce byte-identical ledgers, which means an identical
structural_hash.

Governance Notes:
- Append-only. There is no update, no delete, no reorder.
- record(event_type, payload) -- two arguments, and entries carry the key
  "type", not "event_type". The test suite is canonical on this.
- Payloads are DEEP-COPIED on record. CallerState.snapshot() returns
  self.posterior by reference while every other field is copied; storing
  payload dicts by reference would let a future component mutating a
  caller's posterior in place retroactively alter already-recorded entries.
  That is an append-only violation via aliasing, and it is silent. Copying
  at the boundary closes it here rather than trusting every future caller.
- structural_hash() covers the ledger's SHAPE (the ordered sequence of event
  types), content_hash() covers shape AND payload values. Two explicitly
  labelled hashes rather than one ambiguous "hash", for the same reason
  LatentPayload carries two: "the hash changed" has to mean something
  specific to be worth recording.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TelemetryKernel:
    """Deterministic, append-only event ledger."""

    entries: List[Dict[str, Any]] = field(default_factory=list)

    # ---- writing ----
    def record(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Append one event. Returns the stored entry (already copied)."""
        entry = {
            "seq": len(self.entries),
            "type": str(event_type),
            "payload": copy.deepcopy(payload),
        }
        self.entries.append(entry)
        return entry

    # ---- reading ----
    def __len__(self) -> int:
        return len(self.entries)

    def events_of(self, event_type: str) -> List[Dict[str, Any]]:
        return [e for e in self.entries if e["type"] == event_type]

    def to_list(self) -> List[Dict[str, Any]]:
        return copy.deepcopy(self.entries)

    # ---- hashing ----
    def _canonical(self, include_payload: bool) -> str:
        if include_payload:
            body = [{"seq": e["seq"], "type": e["type"], "payload": e["payload"]}
                    for e in self.entries]
        else:
            body = [{"seq": e["seq"], "type": e["type"]} for e in self.entries]
        return json.dumps(body, sort_keys=True, separators=(",", ":"),
                          default=str)

    def structural_hash(self) -> str:
        """SHA-256 over the ordered sequence of event types only."""
        return hashlib.sha256(
            self._canonical(include_payload=False).encode("utf-8")
        ).hexdigest()

    def content_hash(self) -> str:
        """SHA-256 over event types AND payload values."""
        return hashlib.sha256(
            self._canonical(include_payload=True).encode("utf-8")
        ).hexdigest()


# Historical alias. Several modules and tests import `Telemetry`; the class
# has always been TelemetryKernel.
Telemetry = TelemetryKernel
