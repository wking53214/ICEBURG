"""
Intent.py
---------

The declared reasons a caller rings in. Intent is the caller's own statement
of what they want, and it is the key the routing graph journeys are declared
against -- Simulator._next_node() looks the caller's intent up in the graph's
journey map to decide where they go next.

Correction 4 is why intent is load-bearing rather than descriptive: outcome
classification asks whether the caller reached the point where THEIR declared
intent would be addressed. Iceberg never verifies that the answer given was
correct -- that is post-IVR execution data it cannot see.

RECONSTRUCTED 2026-09-11. The member set is recovered from archive references
(BILLING, TECH_SUPPORT, CANCEL ...) and from the default topology in
Model/Build_Graph.py, which is authoritative on which intents have journeys.
See PROVENANCE.md.
"""

from __future__ import annotations
from enum import Enum
from typing import List


class Intent(str, Enum):
    """Str-valued so snapshots stay JSON-serializable without conversion."""

    BALANCE = "balance"          # self-service exemplar (Correction 3)
    BILLING = "billing"
    TECH_SUPPORT = "tech"
    CANCEL = "cancel"
    UPGRADE = "upgrade"
    COMPLAINT = "complaint"      # straight to a human, no steps
    SALES = "sales"
    GENERAL = "general"          # the honest escape hatch

    @classmethod
    def values(cls) -> List[str]:
        return [m.value for m in cls]

    @classmethod
    def is_known(cls, value: str) -> bool:
        return value in cls.values()
