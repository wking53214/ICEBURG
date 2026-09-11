"""
rl_marl.py
----------

Deterministic multi-agent triage engine. One agent per congested path node,
each producing an independent action distribution over that node's own
congestion signal.

Same tier and same boundary as PPOEngine: this engine NEVER sees an
individual caller. It consumes only the aggregate output of
Aggregation/PathCongestion.py, and its output is a TRIAGE signal -- which
paths are hurting and how much -- not a routing decision and not a staffing
decision. Staffing lives past the ACD door, outside what Iceberg can observe.

KNOWN LIMITATION, open and unresolved in the original system: the agents are
fully independent. There is no coordination modeling, no joint policy, no
communication between agents -- which makes "multi-agent" a description of
the decomposition, not of the learning. This was flagged repeatedly in the
original work and never closed. It is recorded here rather than quietly
fixed, because closing it is a modeling decision that needs real call data.

Governance Notes:
- lr/gamma/eps_clip are config only, stored, not "trained" -- this is
  deterministic policy INFERENCE over fixed, seeded weights.
- Weights are a pure function of self.seed and the agent count, NOT Python's
  built-in hash(), which is randomized per interpreter session and would
  break cross-session replay.

RECONSTRUCTED 2026-09-11 from the archived contract (queue-level,
config-driven, independent agents, PathCongestion input). The original source
was not recovered. See PROVENANCE.md.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

import numpy as np


@dataclass
class MARLEngine:
    lr: float
    gamma: float
    eps_clip: float
    seed: int = 815
    _weight_cache: Dict[int, np.ndarray] = field(
        default_factory=dict, compare=False, repr=False)

    def _weights(self, n: int) -> np.ndarray:
        if n not in self._weight_cache:
            rng = np.random.RandomState(self.seed)
            self._weight_cache[n] = rng.randn(n)
        return self._weight_cache[n]

    def compute_action(self, queues: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """
        Per-agent action distributions. Each agent owns exactly one node and
        scores it against its own {load, peak} pair, independently of every
        other agent -- see the KNOWN LIMITATION above.

        Returns {"agents": {node: {"attention": float, "severity": float}}}
        plus a "probs" view over attention, so the loop can consume this
        engine and PPOEngine through the same key.
        """
        names = sorted(queues.keys())
        if not names:
            return {"agents": {}, "probs": {}}

        base = self._weights(len(names))
        loads = np.array([float(queues[n].get("load", 0.0)) for n in names])
        peaks = np.array([float(queues[n].get("peak", 0.0)) for n in names])

        logits = base * 0.01 + loads
        exp = np.exp(logits - np.max(logits))
        probs = exp / exp.sum()

        agents = {
            n: {"attention": float(p), "severity": float(pk)}
            for n, p, pk in zip(names, probs, peaks)
        }
        return {"agents": agents,
                "probs": {n: a["attention"] for n, a in agents.items()}}
