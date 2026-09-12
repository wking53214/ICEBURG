"""
CallerState.py
--------------

Canonical caller state representation for the GSA.

Best–in–Class Notes:
- Integrated LatentPayload ensures emotional drift is tracked.
- Pure data container; mutated only via simulator step updates.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import sys as _sys
import pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).parent.parent / "Latent"))
from LatentPayload import LatentPayload  # noqa: E402

@dataclass
class DynamicState:
    """Deterministic dynamic metrics updated each step."""
    perceived_wait: float = 0.0
    frustration: float = 0.0
    friction_event: int = 0     # adverse navigation events this step (e.g. misroute)
    actual_wait: float = 0.0    # normalized elapsed queue wait this step
    expected_wait: float = 0.0  # caller's expected wait
    resolved: bool = False      # reached correct agent this step

@dataclass
class CallerState:
    """
    Canonical caller state.
    
    Governance Notes:
    - Requires LatentPayload for full MARL/PPO context.
    - Serialization is strictly JSON–compatible.
    """
    caller_id: str
    intent: str
    emotion: str
    posterior: Dict[str, float] = field(default_factory=dict)
    dynamic: DynamicState = field(default_factory=DynamicState)
    latent: Optional[Any] = None  # Binds LatentPayload to the entity
    next_node: str = "root"
    route: list = field(default_factory=lambda: ["root"])  # full path history for graph-traversal Simulator

    @classmethod
    def new(cls, caller_id: str, intent: str = "billing", emotion: str = "NEUTRAL") -> "CallerState":
        """
        Added 2026-07-01 to match the adopted Simulator(graph, telemetry)
        architecture, which constructs callers via CallerState.new(id) rather
        than the full keyword constructor. Still wires in a real LatentPayload
        by default -- the friction engine stays live regardless of which
        Simulator shape is stepping the caller.
        """
        return cls(
            caller_id=caller_id,
            intent=intent,
            emotion=emotion,
            latent=LatentPayload(),
        )

    def default_likelihoods(self) -> Dict[str, float]:
        """Replay–safe default likelihood initialization."""
        return {
            "billing": 0.25,
            "tech": 0.25,
            "sales": 0.25,
            "cancel": 0.25,
        }

    def snapshot(self) -> Dict[str, Any]:
        """Produces a deterministic snapshot for the ReplayVerifier."""
        return {
            "caller_id": self.caller_id,
            "intent": self.intent,
            "emotion": self.emotion,
            "posterior": self.posterior,
            "dynamic": {
                # All six fields exported (fixed 2026-06-30). Previously only
                # perceived_wait and frustration were captured -- the audit
                # trail could show a caller's final frustration but had zero
                # record of WHY (no friction_event, no wait figures, no
                # resolution flag). That's an unauditable state in the exact
                # system built to prevent them. The friction INPUTS are what
                # let a verifier reconstruct causality, not just the outputs.
                "perceived_wait": self.dynamic.perceived_wait,
                "frustration": self.dynamic.frustration,
                "friction_event": self.dynamic.friction_event,
                "actual_wait": self.dynamic.actual_wait,
                "expected_wait": self.dynamic.expected_wait,
                "resolved": self.dynamic.resolved,
            },
            "latent": self.latent.to_dict() if self.latent else None,
            "next_node": self.next_node,
            "route": list(self.route),
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.snapshot()

