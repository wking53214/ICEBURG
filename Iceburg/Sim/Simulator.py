"""
Simulator.py -- v2 (2026-07-02)

Deterministic per-caller graph-traversal engine.

REWRITTEN 2026-07-01. This replaces the earlier Simulator design (which took
routing/staffing/bayes/queues/recorder/governance as injected per-step
dependencies). That design was fixed and proven live earlier the same day --
3 integration tests, 4000 fuzz trajectories -- but turned out to diverge from
the architecture six independent test files (among them test_simulator_core,
test_cluster_runner, test_rl_ppo and test_rl_marl) all consistently assumed.

CORRECTED 2026-07-02 for the four locked domain corrections (see
ARCHITECTURE.md). Traversal is now journey-based rather than keyed off the
f"{intent}_queue" string rule, because queue nodes no longer exist
(Correction 1). Termination classification is binary and structural
(Correction 4). update_queue is DELETED -- it maintained "current occupants"
of a place that cannot exist.

The split:
- Simulator: simple, deterministic, NO ML. Walks one caller through the
  graph. Routing at a branch point follows the caller's own declared
  journey -- no policy engine needed for that decision.
- PPOEngine / MARLEngine (Engines/): the actual ML layer, operates ONLY on
  aggregated path congestion, never on an individual caller. Not called from
  here. This is the queue-level "transmission" layer -- genuinely separate
  from per-caller traversal, not injected into it.

The earlier staffing engine was removed 2026-07-02 (not demoted, not stubbed
-- deleted).
Iceberg's objective ends at the ACD door: it finds and reduces pre-ACD
friction, it does not measure its own success (that's containment, measured
externally via inbound-vs-offered call ratios) and it does not make staffing
decisions. Staffing math requires AHT, shrinkage, and answered-vs-offered
data -- none of which Iceberg can ever observe, since none of it exists
before a caller crosses into the ACD. Not a scope preference; epistemically
impossible from where this system sits.

The friction engine (LatentPayload/DynamicState) is preserved exactly as
built and hardened -- it evolves every step regardless of which Simulator
shape is doing the stepping, since frustration/trust are properties of the
caller, not of the routing mechanism.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class Simulator:
    """
    Deterministic graph-traversal simulator.

    Governance Notes:
    - No trained/learned ML in the per-step path -- that's a separate,
      queue-level layer (see module docstring). This does NOT mean the step
      is behavior-free -- LatentPayload's deterministic frustration/trust
      rules still run every step. "No ML" means no policy inference happens
      here, not "nothing behavioral happens here."
    - max_steps is enforced PER CALLER, using caller.latent.step_index, which
      already existed as a per-caller counter. A SIMULATOR-wide counter would
      be wrong (a multi-caller determinism test in the original private
      suite steps 3 different callers 5 times each = 15 total calls through
      one instance).
    """
    graph: Any
    telemetry: Any
    max_steps: int = 815

    def __post_init__(self):
        """
        Light shape validation at construction instead of a confusing
        AttributeError deep inside traversal. RoutingGraph.validate() already
        checks neighbor-reference integrity at build_graph() time -- this is a
        cheaper, separate check that graph itself looks like a RoutingGraph at
        all, in case one is ever constructed by hand and passed in directly.
        """
        if not hasattr(self.graph, "nodes"):
            raise ValueError(
                "Simulator.graph must expose a .nodes mapping (got: %r)"
                % type(self.graph)
            )

    def _next_node(self, caller: "CallerState") -> str:
        """
        Deterministic traversal, journey-based (replaces the {intent}_queue
        string rule, which named a node kind that no longer exists).

        Terminal: stay. Journey successor if defined and legal. Single
        neighbor: follow. A branch with no declared journey raises
        RuntimeError -- refusing to route a caller down a path nobody declared
        is preferable to silently picking one.
        """
        current = caller.route[-1] if caller.route else "root"
        node = self.graph.nodes.get(current)
        if node is None or not node.neighbors:
            return current
        nxt = self.graph.journey_next(caller.intent, current)
        if nxt is not None and nxt in node.neighbors:
            return nxt
        if len(node.neighbors) == 1:
            return node.neighbors[0]
        raise RuntimeError(
            f"GSA Violation: intent '{caller.intent}' has no journey through "
            f"branch '{current}' -- refusing to route a caller down a path "
            f"nobody declared."
        )

    def step(self, caller: "CallerState") -> dict:
        """
        Advance one caller by one step: traverse the graph, evolve latent
        state, record a full-state telemetry snapshot for replay.

        Returns moved/content_hash/structural_hash alongside
        caller_id/next_node. Two separate, explicitly-labeled hash keys
        rather than one ambiguous "hash" -- collapsing them would reopen the
        exact "does hash-changed mean real-state-changed" ambiguity
        content_hash/structural_hash were built to resolve.
        """
        if caller.latent is not None and caller.latent.step_index >= self.max_steps:
            raise RuntimeError(
                f"GSA Violation: caller {caller.caller_id} exceeded "
                f"max_steps ({self.max_steps})."
            )

        current = caller.route[-1] if caller.route else "root"
        if self.graph.kind_of(current) != "step":
            raise RuntimeError(
                f"GSA Violation: caller {caller.caller_id} is at "
                f"intent-addressed marker '{current}' -- past the door. No "
                f"step, no latent evolution, no data exists here "
                f"(Correction 2)."
            )

        next_node = self._next_node(caller)
        moved = next_node != current

        if moved:
            caller.route.append(next_node)
        caller.next_node = next_node

        # Latent evolution: unchanged logic from the hardened friction engine.
        # Runs every step regardless of graph movement -- frustration/trust
        # are about what happened to the caller, not about whether they moved
        # to a new node this particular step.
        if caller.latent is not None:
            caller.latent.update_after_step(caller.dynamic)

        if self.telemetry is not None:
            self.telemetry.record("step", {
                "caller_id": caller.caller_id,
                "state": caller.to_dict(),
            })

        result = {"caller_id": caller.caller_id,
                  "next_node": next_node, "moved": moved}
        if caller.latent is not None:
            result["content_hash"] = caller.latent.content_hash()
            result["structural_hash"] = caller.latent.structural_hash()
        return result

    def divert(self, caller: "CallerState") -> dict:
        """
        System-initiated escape to a human mid-journey (0-out, 'agent',
        repeated-failure policy). Follows the node's unique handoff-kind
        neighbor. Latent still evolves -- the divert transition is an
        IVR-scope event, often a high-friction one.
        """
        current = caller.route[-1] if caller.route else "root"
        node = self.graph.nodes[current]
        escapes = [n for n in node.neighbors
                   if self.graph.kind_of(n) == "handoff"]
        if len(escapes) != 1:
            raise RuntimeError(
                f"GSA Violation: no deterministic escape from {current} "
                f"(found {len(escapes)})"
            )
        caller.route.append(escapes[0])
        caller.next_node = escapes[0]
        if caller.latent is not None:
            caller.latent.update_after_step(caller.dynamic)
        if self.telemetry is not None:
            self.telemetry.record("step", {"caller_id": caller.caller_id,
                                           "diverted": True,
                                           "state": caller.to_dict()})
        result = {"caller_id": caller.caller_id, "next_node": escapes[0],
                  "moved": True, "diverted": True}
        if caller.latent is not None:
            result["content_hash"] = caller.latent.content_hash()
            result["structural_hash"] = caller.latent.structural_hash()
        return result

    def record_termination(self, caller: "CallerState") -> dict:
        """
        Correction 4: BINARY and STRUCTURAL. success <=> the route touched an
        intent-addressed marker (resolution OR handoff -- both first-class);
        abandonment <=> it did not. No threshold participates in this
        determination; there is nothing here for a client to declare.
        peak_frustration is recorded as a SEVERITY signal for triage --
        how bad, never whether.
        """
        route = list(caller.route)
        res, hof = self.graph.resolution_nodes(), self.graph.handoff_nodes()
        marker = next((n for n in route if n in res or n in hof), None)
        if marker is None:
            outcome, path = "abandonment", None
        else:
            path = "self_service" if marker in res else "handoff"
            outcome = "success"
        peak = caller.latent.peak_frustration if caller.latent is not None else 0.0
        record = {
            "caller_id": caller.caller_id,
            "intent": caller.intent,
            "outcome": outcome,                    # "success" | "abandonment"
            "outcome_path": path,                  # "self_service"|"handoff"|None
            "marker_node": marker,                 # which door, or None
            "peak_frustration": float(peak),       # severity, NOT classifier
            "final_frustration": float(caller.dynamic.frustration),
            "route_length": len(route),
        }
        if self.telemetry is not None:
            self.telemetry.record("termination", record)
        return record

    # update_queue: DELETED. It maintained "current occupants" of a place
    # that cannot exist (Correction 1). Not stubbed, not deprecated -- gone,
    # same treatment the earlier staffing engine got.
