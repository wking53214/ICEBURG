"""
IntegrationLoop.py -- Tier 3.5 integration loop (v2, 2026-07-02).

The loop is the only place the three tiers meet. It owns the tick, and each
tick runs four ordered phases:

  Phase A  step (or divert, or hang up) every active caller
  Phase B  group the survivors by their CURRENT node -- step-kind nodes only
  Phase C  aggregate those groups into per-path congestion, hand it to the
           triage engine
  Phase D  sweep every caller now standing on a terminal marker

CORRECTED 2026-07-02. Phase B's old f"{name}_queue" suffix filter is replaced
by a node-kind filter: callers standing at a marker have crossed the boundary
(Correction 2) and never aggregate -- there is no data past the door.
Aggregation moved from QueueStress.compute_queue_loads() to
PathCongestion.compute_path_congestion() to match.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Set

import sys as _sys
import pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).parent.parent / "Aggregation"))
from PathCongestion import compute_path_congestion  # noqa: E402


@dataclass
class IntegrationLoop:
    simulator: Any            # Simulator (graph + telemetry inside)
    engine: Any               # PPOEngine
    telemetry: Any            # ledger the loop writes its tick events to
    max_ticks: int = 10_000
    stimuli: Dict[Tuple[int, str], Dict[str, Any]] = field(default_factory=dict)
    diversions: Set[Tuple[int, str]] = field(default_factory=set)
    hangups: Set[Tuple[int, str]] = field(default_factory=set)

    def _node(self, c) -> str:
        return c.route[-1] if c.route else "root"

    def _is_terminal(self, c) -> bool:
        # Markers have no neighbors, so the no-neighbors check already sweeps
        # them the same tick they are reached.
        n = self.simulator.graph.nodes.get(self._node(c))
        return n is None or not n.neighbors

    def _apply_stimulus(self, tick: int, c) -> None:
        f = self.stimuli.get((tick, c.caller_id))
        if f:
            for k in sorted(f):
                setattr(c.dynamic, k, f[k])

    def _terminate(self, active: Dict[str, Any], cid: str) -> None:
        self.simulator.record_termination(active[cid])
        del active[cid]

    def run(self, initial_callers: List[Any]) -> Dict[str, Any]:
        ids = [c.caller_id for c in initial_callers]
        if len(set(ids)) != len(ids):
            raise ValueError("GSA Violation: duplicate caller_id in population")
        unknown = sorted(c.intent for c in initial_callers
                         if c.intent not in self.simulator.graph.journeys)
        if unknown:
            raise ValueError(f"GSA Violation: intents without journeys: {unknown}")

        active = {c.caller_id: c for c in initial_callers}
        tick, terminated = 0, 0

        self.telemetry.record("loop_start", {
            "callers": sorted(active),
            # The marker set and journey spec must be reconstructable from the
            # ledger alone -- an audit cannot depend on the code still existing
            # in the shape it had at run time.
            "graph": self.simulator.graph.to_dict(),
            "diversions": [list(d) for d in sorted(self.diversions)],
            "hangups": [list(h) for h in sorted(self.hangups)],
        })

        while active:
            if tick >= self.max_ticks:
                raise RuntimeError(
                    f"GSA Violation: max_ticks exhausted, {sorted(active)} "
                    f"still active"
                )

            # Phase A -- advance every caller. A hangup takes precedence over
            # a diversion: the caller's act preempts the system's.
            hung_up: List[str] = []
            for cid in sorted(active):
                if (tick, cid) in self.hangups:
                    self._terminate(active, cid)
                    hung_up.append(cid)
                    terminated += 1
                    continue
                self._apply_stimulus(tick, active[cid])
                if (tick, cid) in self.diversions:
                    self.simulator.divert(active[cid])
                else:
                    self.simulator.step(active[cid])

            # Phase B -- group by current node, step-kind nodes only.
            node_snapshots: Dict[str, List[Dict[str, Any]]] = {}
            for cid in sorted(active):
                node = self._node(active[cid])
                if self.simulator.graph.kind_of(node) == "step":
                    node_snapshots.setdefault(node, []).append(
                        active[cid].snapshot())

            # Phase C -- aggregate, then triage.
            loads = compute_path_congestion(node_snapshots)
            triage = self.engine.compute_action(loads)["probs"]

            # Phase D -- sweep terminal markers.
            for cid in sorted(active):
                if self._is_terminal(active[cid]):
                    self._terminate(active, cid)
                    terminated += 1

            self.telemetry.record("tick_summary", {
                "tick": tick,
                "path_congestion": loads,
                "triage": triage,
                "hung_up": hung_up,
                "active_after": sorted(active),
            })
            tick += 1

        return {"ticks": tick, "terminated": terminated,
                "ledger_hash": self.telemetry.structural_hash()}
