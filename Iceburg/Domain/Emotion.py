"""
Emotion.py
----------

Coarse emotional labels carried on CallerState.emotion.

This is a LABEL, not the friction model. The real emotional dynamics live in
Latent/LatentPayload.py -- frustration, trust, volatility, memory -- and they
evolve deterministically every step. This enum exists so a snapshot can carry
a human-readable starting disposition and so ingest adapters have a fixed
vocabulary to map into.

Deliberately coarse: nothing in the engine branches on it. Anything that
needs to reason about how a caller is actually doing reads LatentPayload.

RECONSTRUCTED 2026-09-11. CallerState.new() defaults emotion to "NEUTRAL",
which is the one member the archive pins exactly. See PROVENANCE.md.
"""

from __future__ import annotations
from enum import Enum
from typing import List


class Emotion(str, Enum):
    """Str-valued so snapshots stay JSON-serializable without conversion."""

    CALM = "CALM"
    NEUTRAL = "NEUTRAL"          # CallerState.new() default
    IMPATIENT = "IMPATIENT"
    FRUSTRATED = "FRUSTRATED"
    ANGRY = "ANGRY"

    @classmethod
    def values(cls) -> List[str]:
        return [m.value for m in cls]
