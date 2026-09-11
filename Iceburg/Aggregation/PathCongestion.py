"""
PathCongestion.py -- Tier 3 aggregation (replaces QueueStress).

Groups CURRENT snapshots of ACTIVE callers by the node they are at right
now (Fork D). This measures CO-NAVIGATION -- an instantaneous coincidence
of moving callers at the same menu -- not occupancy of a queue, which
cannot exist (Correction 1). No history, no counters, no dwelling: a pure
function of this tick's snapshots. Output shape {load, peak, breadth, n}
is preserved exactly so PPOEngine/MARLEngine consume it unchanged; only
the key semantics move from queue-name to node-name.
"""
import math
from typing import Dict, Any, List

W_FRUSTRATION = 0.30
W_TRUST_DECAY = 0.25
W_FRICTION    = 0.25
W_VOLATILITY  = 0.10
W_MEMORY      = 0.10
FRICTION_NORM = 20.0
PEAK_WEIGHT   = 0.6


def _clamp01(x: float) -> float:
    return max(0.0, min(float(x), 1.0))


def _caller_distress(snap: Dict[str, Any]) -> float:
    # Unchanged from QueueStress -- distress is caller-borne (LatentPayload
    # doctrine: misroute is misroute, wherever it happens).
    dyn = snap.get("dynamic") or {}
    lat = snap.get("latent")
    f = _clamp01(dyn.get("frustration", 0.0))
    if lat is None:
        return f
    tb = lat.get("trust_baseline")
    ts = _clamp01(lat.get("trust_scalar", 0.5))
    td = _clamp01((ts if tb is None else float(tb)) - ts)
    fc = _clamp01(float(lat.get("friction_count", 0)) / FRICTION_NORM)
    return (W_FRUSTRATION * f + W_TRUST_DECAY * td + W_FRICTION * fc
            + W_VOLATILITY * _clamp01(lat.get("volatility", 0.0))
            + W_MEMORY * _clamp01(lat.get("memory_flag", 0.0)))


def compute_path_congestion(
    node_snapshots: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, float]]:
    """node_snapshots: current-node-name -> snapshots of callers there NOW.
    Caller (the loop) supplies step-kind nodes only; markers never appear."""
    out = {}
    for name, snaps in node_snapshots.items():
        if not snaps:
            out[name] = {"load": 0.0, "peak": 0.0, "breadth": 0.0, "n": 0.0}
            continue
        ordered = sorted(snaps, key=lambda s: str(s.get("caller_id", "")))
        scores = [_caller_distress(s) for s in ordered]
        breadth = math.fsum(scores) / len(scores)
        peak = max(scores)
        load = _clamp01((1 - PEAK_WEIGHT) * breadth + PEAK_WEIGHT * peak)
        out[name] = {"load": load, "peak": peak,
                     "breadth": breadth, "n": float(len(scores))}
    return out
