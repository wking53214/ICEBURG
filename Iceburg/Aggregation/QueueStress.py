"""
QueueStress.py -- Tier 3 aggregation. SUPERSEDED by PathCongestion.py.

*** THIS MODULE IS RETAINED FOR LINEAGE ONLY. NOTHING IMPORTS IT. ***

It rolled the "current occupants" of a queue into one per-queue stress
concentration. Correction 1 retired it: a queue does not exist in an IVR,
only directionality. There is no such thing as "3 people waiting in the
billing queue" inside an IVR, so there is nothing here to aggregate.

Aggregation/PathCongestion.py replaces it. The distress math is carried over
UNCHANGED -- distress is caller-borne, and misroute is misroute wherever it
happens -- and the output shape {load, peak, breadth, n} is identical, so
PPOEngine and MARLEngine consume the replacement without modification. Only
the key semantics moved, from queue-name to node-name.

Kept rather than deleted because the two files side by side are the clearest
statement of what Correction 1 actually changed, and what it deliberately did
not. New code must import PathCongestion.
"""

import math
from typing import Any, Dict, List


def _clamp01(x: float) -> float:
    return max(0.0, min(float(x), 1.0))

def _caller_distress(snap: Dict[str, Any]) -> float:
    dyn = snap.get("dynamic") or {}
    lat = snap.get("latent")

    # R-1: frustration clamped. Upstream unboundedness is LatentPayload's
    # open issue; here, "maximally frustrated" saturates at 1.0.
    f = _clamp01(dyn.get("frustration", 0.0))

    # R-4: a caller with no latent payload contributes frustration only.
    # Documented degradation, not a crash.
    if lat is None:
        return f

    # R-2: decay floored at 0. Trust above baseline earns NOTHING here --
    # relief overshoot is LatentPayload's reward, never aggregation credit.
    tb = lat.get("trust_baseline")
    ts = _clamp01(lat.get("trust_scalar", 0.5))
    td = _clamp01((ts if tb is None else float(tb)) - ts)  # None -> decay 0

    # R-5: coupled to LatentPayload._FRICTION_CAP by documentation, not import.
    fc = _clamp01(float(lat.get("friction_count", 0)) / FRICTION_NORM)

    return (W_FRUSTRATION * f + W_TRUST_DECAY * td + W_FRICTION * fc
            + W_VOLATILITY * _clamp01(lat.get("volatility", 0.0))
            + W_MEMORY * _clamp01(lat.get("memory_flag", 0.0)))


def compute_queue_loads(
    queue_snapshots: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, float]]:
    out = {}
    for name, snaps in queue_snapshots.items():
        if not snaps:
            out[name] = {"load": 0.0, "peak": 0.0, "breadth": 0.0, "n": 0.0}
            continue
        # R-3: canonical order by caller_id, and math.fsum (exact,
        # order-independent sum) -- identical SET of readings gives a
        # bit-identical result, hence a stable SHA-256.
        ordered = sorted(snaps, key=lambda s: str(s.get("caller_id", "")))
        scores = [_caller_distress(s) for s in ordered]
        breadth = math.fsum(scores) / len(scores)
        peak = max(scores)
        load = _clamp01((1 - PEAK_WEIGHT) * breadth + PEAK_WEIGHT * peak)
        out[name] = {"load": load, "peak": peak,
                     "breadth": breadth, "n": float(len(scores))}
    return out
