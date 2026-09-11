"""
IngestAdapter.py -- Tier "on-ramp": turns a raw call-event log into the
friction stimuli Iceberg's real Simulator/IntegrationLoop already knows how
to consume.

Two halves, deliberately kept separate:

1. Synthetic event log generator -- produces call logs shaped the way a real
   telephony/IVR platform export looks (call_start, menu_reached, hold
   segments, transfer, resolved, call_end), NOT a hand-built simulation
   population. This is the stand-in for a real partner's data until one
   exists.

2. The adapter itself (`derive_stimuli`) -- pure, mechanical translation from
   raw events to friction fields. No modeling judgment calls live here:
   - friction_event: 1 if this hop revisits a node already in the caller's
     route this call (backtrack/loop), OR if the dwell time before this hop
     exceeds an expected-dwell threshold for the node it's leaving. Both are
     derivable from (timestamp, node) alone.
   - actual_wait: sum of hold_start/hold_end segment durations for the call
     so far, in seconds.
   - resolved: True the instant the call's terminal node is a resolution or
     handoff marker (mirrors Simulator.record_termination's own binary,
     structural rule -- reused here on purpose, not reinvented).

   expected_wait and the dwell-anomaly threshold are the one deliberately
   NOT-yet-decided input -- flagged inline, not guessed at.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple
import random


# ---------------------------------------------------------------------------
# 1. Synthetic event log generator
# ---------------------------------------------------------------------------

# NOTE: expected dwell per node is a placeholder baseline (flat 8s), same
# "unvalidated constant, sane not calibrated" category as the rest of the
# codebase's tunables. This is the open question from the friction_event
# rule -- not resolved here, just given a value so the mechanical half is
# runnable and testable.
DEFAULT_EXPECTED_DWELL_SECONDS = 8.0


def generate_synthetic_call(
    call_id: str,
    journey: List[str],
    rng: random.Random,
    friction_profile: str = "clean",
) -> List[Dict[str, Any]]:
    """
    Produces one call's raw event log, shaped like a real platform export.

    friction_profile:
      - "clean"    -- moves straight down the journey, normal dwell times.
      - "revisit"  -- backtracks to an earlier node once mid-journey.
      - "overrun"  -- one hop takes far longer than expected (long hold).
      - "hangup"   -- caller abandons partway, never reaches a marker.
    """
    t = 0.0
    events = [{"call_id": call_id, "type": "call_start", "timestamp": t}]

    path = list(journey)
    if friction_profile == "hangup":
        # Truncate before the terminal marker -- caller never arrives.
        cut = max(1, len(path) - 1)
        path = path[:cut]

    visited: List[str] = []
    for i, node in enumerate(path):
        # normal inter-node dwell
        dwell = rng.uniform(3.0, 6.0)

        if friction_profile == "overrun" and i == len(path) // 2:
            dwell = DEFAULT_EXPECTED_DWELL_SECONDS * 4  # deliberate overrun

        t += dwell
        events.append({"call_id": call_id, "type": "menu_reached",
                        "node": node, "timestamp": t})
        visited.append(node)

        if friction_profile == "revisit" and i == len(path) // 2 and len(visited) >= 2:
            # caller bounces back to the previous node once, then continues
            back_node = visited[-2]
            t += rng.uniform(3.0, 5.0)
            events.append({"call_id": call_id, "type": "menu_reached",
                            "node": back_node, "timestamp": t})
            t += rng.uniform(3.0, 5.0)
            events.append({"call_id": call_id, "type": "menu_reached",
                            "node": node, "timestamp": t})

        # occasional hold segment (queueing/auth check) on any hop
        if rng.random() < 0.3:
            hold = rng.uniform(2.0, 10.0)
            events.append({"call_id": call_id, "type": "hold_start", "timestamp": t})
            t += hold
            events.append({"call_id": call_id, "type": "hold_end", "timestamp": t})

    disposition = "hangup" if friction_profile == "hangup" else "completed"
    events.append({"call_id": call_id, "type": "call_end", "timestamp": t,
                    "disposition": disposition})
    return events


def generate_population(
    journeys: Dict[str, List[str]],
    n_calls: int,
    seed: int = 815,
) -> List[List[Dict[str, Any]]]:
    """Deterministic (seeded) population of synthetic calls across intents
    and friction profiles, mimicking a realistic mixed call log."""
    rng = random.Random(seed)
    profiles = ["clean", "clean", "revisit", "overrun", "hangup"]
    intents = list(journeys.keys())
    out = []
    for i in range(n_calls):
        intent = intents[i % len(intents)]
        profile = profiles[i % len(profiles)]
        call_id = f"C{i:04d}"
        out.append(generate_synthetic_call(call_id, journeys[intent], rng, profile))
    return out


# ---------------------------------------------------------------------------
# 2. The adapter -- mechanical friction derivation
# ---------------------------------------------------------------------------

@dataclass
class DerivedCall:
    call_id: str
    route: List[str]
    # per-hop stimulus, in the shape IntegrationLoop.stimuli expects per
    # (tick, caller_id): friction_event/actual_wait/expected_wait/resolved
    stimuli_by_hop: List[Dict[str, Any]] = field(default_factory=list)
    final_outcome_hint: str = "unknown"  # "success" / "abandonment", derived
                                          # here for sanity-checking only --
                                          # the real classifier is
                                          # Simulator.record_termination, not
                                          # this adapter.


def derive_stimuli(
    events: List[Dict[str, Any]],
    resolution_nodes: frozenset,
    handoff_nodes: frozenset,
    dwell_anomaly_seconds: float = DEFAULT_EXPECTED_DWELL_SECONDS,
    expected_wait_seconds: float = DEFAULT_EXPECTED_DWELL_SECONDS,
    expected_wait_by_node: Dict[str, float] | None = None,
) -> DerivedCall:
    """
    Pure, mechanical translation. No modeling judgment: every derived value
    is a direct function of (timestamp, node) pairs already in the log.
    """
    call_id = events[0]["call_id"]
    menu_events = [e for e in events if e["type"] == "menu_reached"]

    route: List[str] = []
    stimuli: List[Dict[str, Any]] = []

    # CORRECTIONS 2026-07-03, found by execution-tracing, not review:
    #   BUG 1 (fixed): actual_wait was cumulative across the whole call, so
    #     one early hold re-tripped LatentPayload's actual>expected gate on
    #     every later hop -- repeated friction charges for a single wait.
    #     Now: per-hop, attributed to the node where the waiting happened.
    #   BUG 2 (fixed): the dwell-anomaly gate used raw inter-menu gap, which
    #     INCLUDES hold time -- so any hold >8s also fired the dwell gate,
    #     double-counting one wait through two independent gates and
    #     drowning out expected_wait's own effect entirely.
    #     Now: dwell is net transit time, holds subtracted out.
    hold_segments: List[Tuple[float, float]] = []
    open_hold_start = None
    for e in sorted(events, key=lambda e: e["timestamp"]):
        if e["type"] == "hold_start":
            open_hold_start = e["timestamp"]
        elif e["type"] == "hold_end" and open_hold_start is not None:
            hold_segments.append((open_hold_start, e["timestamp"]))
            open_hold_start = None

    def hold_between(t0: float, t1: float) -> float:
        """Total hold time overlapping the window [t0, t1)."""
        return sum(max(0.0, min(end, t1) - max(start, t0))
                   for start, end in hold_segments if end > t0 and start < t1)

    call_end_ts = events[-1]["timestamp"]
    prev_t = events[0]["timestamp"]
    for i, e in enumerate(menu_events):
        node = e["node"]
        ts = e["timestamp"]
        next_ts = (menu_events[i + 1]["timestamp"]
                   if i + 1 < len(menu_events) else call_end_ts)

        # Net transit time INTO this node: raw gap minus any hold inside it.
        dwell_net = (ts - prev_t) - hold_between(prev_t, ts)
        # Wait AT this node: holds between arriving here and leaving.
        hold_here = hold_between(ts, next_ts)

        revisit = node in route  # mechanical: already in this call's route
        overrun = dwell_net > dwell_anomaly_seconds
        friction_event = 1 if (revisit or overrun) else 0

        expected_here = (
            expected_wait_by_node.get(node, expected_wait_seconds)
            if expected_wait_by_node else expected_wait_seconds
        )

        route.append(node)
        stimuli.append({
            "node": node,
            "timestamp": ts,
            "friction_event": friction_event,
            "actual_wait": hold_here,
            "expected_wait": expected_here,
            "resolved": node in resolution_nodes or node in handoff_nodes,
        })
        prev_t = ts

    last_node = route[-1] if route else None
    if last_node in resolution_nodes or last_node in handoff_nodes:
        outcome_hint = "success"
    else:
        outcome_hint = "abandonment"

    return DerivedCall(call_id=call_id, route=route,
                        stimuli_by_hop=stimuli, final_outcome_hint=outcome_hint)
