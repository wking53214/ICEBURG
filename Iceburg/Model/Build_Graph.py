"""
Build_Graph.py -- v2 (2026-07-02)

Corrected routing graph for Iceberg. QUEUE NODES REMOVED ENTIRELY
(Correction 1: "a queue doesn't exist in an IVR, only directionality").

Node kinds:
  step       -- a place the caller is moving THROUGH (menu, auth, prompt)
  resolution -- the instant a self-service intent is addressed (Correction 3)
  handoff    -- the instant the door to the ACD opens (Correction 2)

resolution/handoff nodes are TERMINAL (no neighbors). They are markers a
route ends at, not places anyone dwells: the loop sweeps a caller off them
the same tick they arrive. Both marker kinds are first-class success points
(Correction 4).

Journeys are declared per intent as data (Fork A): depth is configuration,
because depth IS the lever Iceberg optimizes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

NODE_STEP = "step"
NODE_RESOLUTION = "resolution"
NODE_HANDOFF = "handoff"
MARKER_KINDS = (NODE_RESOLUTION, NODE_HANDOFF)


@dataclass
class GraphNode:
    name: str
    neighbors: List[str] = field(default_factory=list)
    kind: str = NODE_STEP

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "neighbors": list(self.neighbors),
                "kind": self.kind}


@dataclass
class RoutingGraph:
    nodes: Dict[str, GraphNode]
    journeys: Dict[str, List[str]]        # intent -> full path, root..terminal
    marker_owner: Dict[str, str] = field(default_factory=dict)  # marker -> intent

    def __post_init__(self):
        # Precomputed successor map: intent -> {node -> next node}. O(1),
        # deterministic, replaces the old stringly f"{intent}_queue" rule.
        self._journey_next: Dict[str, Dict[str, str]] = {
            intent: {path[i]: path[i + 1] for i in range(len(path) - 1)}
            for intent, path in self.journeys.items()
        }
        self._resolution = frozenset(n for n, nd in self.nodes.items()
                                     if nd.kind == NODE_RESOLUTION)
        self._handoff = frozenset(n for n, nd in self.nodes.items()
                                  if nd.kind == NODE_HANDOFF)

    # ---- queries used by Simulator / Loop / classification ----
    def kind_of(self, name: str) -> str:
        return self.nodes[name].kind

    def journey_next(self, intent: str, node: str) -> Optional[str]:
        return self._journey_next.get(intent, {}).get(node)

    def resolution_nodes(self) -> frozenset:
        return self._resolution

    def handoff_nodes(self) -> frozenset:
        return self._handoff

    def marker_nodes(self) -> frozenset:
        return self._resolution | self._handoff

    # ---- integrity ----
    def validate(self) -> None:
        for name, node in self.nodes.items():
            if node.kind not in (NODE_STEP,) + MARKER_KINDS:
                raise ValueError(f"Integrity Error: {name} illegal kind {node.kind}")
            for nb in node.neighbors:
                if nb not in self.nodes:
                    raise ValueError(f"Integrity Error: {name} -> {nb} (Missing)")
            if node.kind in MARKER_KINDS and node.neighbors:
                raise ValueError(f"Integrity Error: marker {name} must be terminal "
                                 f"(Correction 2/3: markers are instants, not places)")
            if node.kind == NODE_STEP:
                # An "escape" is a handoff neighbor reachable ONLY by divert --
                # the 0-out. A handoff that is some intent's declared journey
                # successor from this node is a routing target, not an escape:
                # intent_menu legitimately fans out to several intents, and
                # complaint/general go straight to a human with no steps in
                # between, so their handoff markers are menu children.
                # Counting those as escapes made the default topology fail its
                # own validator.
                # RECONSTRUCTION FIX 2026-09-11: the v2 design block this file
                # was recovered from raised on build_graph() as written; see
                # PROVENANCE.md. The rule's stated purpose -- "max 1 for
                # deterministic divert" -- is preserved exactly.
                declared = {nxt for succ in self._journey_next.values()
                            for src, nxt in succ.items() if src == name}
                escapes = [nb for nb in node.neighbors
                           if self.nodes[nb].kind == NODE_HANDOFF
                           and nb not in declared]
                if len(escapes) > 1:
                    raise ValueError(f"Integrity Error: {name} has {len(escapes)} "
                                     f"handoff escapes; max 1 for deterministic divert")
        for intent, path in self.journeys.items():
            if not path or path[0] != "root":
                raise ValueError(f"Integrity Error: journey {intent} must start at root")
            if self.nodes[path[-1]].kind not in MARKER_KINDS:
                raise ValueError(f"Integrity Error: journey {intent} must end at a marker")
            for a, b in zip(path, path[1:]):
                if b not in self.nodes[a].neighbors:
                    raise ValueError(f"Integrity Error: journey {intent} uses "
                                     f"non-edge {a} -> {b}")
                if b != path[-1] and self.nodes[b].kind != NODE_STEP:
                    raise ValueError(f"Integrity Error: journey {intent} passes "
                                     f"THROUGH marker {b}")

    def to_dict(self) -> Dict[str, Any]:
        # JSON-safe, deterministic (insertion order = declaration order).
        return {
            "nodes": {n: nd.to_dict() for n, nd in self.nodes.items()},
            "journeys": {i: list(p) for i, p in self.journeys.items()},
            "marker_owner": dict(self.marker_owner),
            "resolution_nodes": sorted(self._resolution),
            "handoff_nodes": sorted(self._handoff),
        }


class GraphBuilder:
    """Fluent, declaration-order-deterministic builder."""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.journeys: Dict[str, List[str]] = {}
        self.marker_owner: Dict[str, str] = {}
        self._menu_children: List[str] = []

    def _node(self, name: str, kind: str) -> str:
        if name in self.nodes:
            raise ValueError(f"Duplicate node {name}")
        self.nodes[name] = GraphNode(name, [], kind)
        return name

    def self_service(self, intent: str, steps: List[str],
                     resolution: str) -> "GraphBuilder":
        """Journey ending at a self-service resolution point. Every step
        also gets an escape edge to this intent's handoff (the 0-out)."""
        esc = self._node(f"{intent}::handoff", NODE_HANDOFF)
        res = self._node(f"{intent}::{resolution}", NODE_RESOLUTION)
        self.marker_owner[esc] = intent
        self.marker_owner[res] = intent
        chain = [self._node(f"{intent}::{s}", NODE_STEP) for s in steps]
        for i, n in enumerate(chain):
            nxt = chain[i + 1] if i + 1 < len(chain) else res
            self.nodes[n].neighbors = [nxt, esc]
        first = chain[0] if chain else res
        self._menu_children.append(first)
        self.journeys[intent] = ["root", "intent_menu"] + chain + [res]
        return self

    def handoff(self, intent: str, steps: List[str] = ()) -> "GraphBuilder":
        """Journey ending at a handoff point (a human is the destination)."""
        hof = self._node(f"{intent}::handoff", NODE_HANDOFF)
        self.marker_owner[hof] = intent
        chain = [self._node(f"{intent}::{s}", NODE_STEP) for s in steps]
        for i, n in enumerate(chain):
            nxt = chain[i + 1] if i + 1 < len(chain) else hof
            self.nodes[n].neighbors = [nxt] if nxt == hof else [nxt, hof]
        first = chain[0] if chain else hof
        self._menu_children.append(first)
        self.journeys[intent] = ["root", "intent_menu"] + chain + [hof]
        return self

    def build(self) -> RoutingGraph:
        self.nodes = {"root": GraphNode("root", ["intent_menu"], NODE_STEP),
                      "intent_menu": GraphNode("intent_menu",
                                               list(self._menu_children),
                                               NODE_STEP),
                      **self.nodes}
        g = RoutingGraph(self.nodes, self.journeys, self.marker_owner)
        g.validate()
        return g


def build_graph() -> RoutingGraph:
    """Default topology. balance is the self-service exemplar, deliberately
    buried 5 deep (auth -> menu_1 -> menu_2 -> menu_3 -> delivery) -- the
    'before' picture. Menu position/depth is itself a client lever."""
    b = GraphBuilder()
    b.self_service("balance", ["auth", "menu_1", "menu_2", "menu_3"], "delivery")
    b.handoff("billing", ["auth"])
    b.handoff("tech", ["auth"])
    b.handoff("cancel", ["auth"])
    b.handoff("upgrade", ["auth"])
    b.handoff("complaint")          # straight to a human -- Help is its own thing
    b.handoff("sales", ["auth"])
    b.handoff("general")            # the honest escape hatch
    return b.build()
