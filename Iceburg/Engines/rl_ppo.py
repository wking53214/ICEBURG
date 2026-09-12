"""
rl_ppo.py
---------

Deterministic, queue-level PPO policy engine.

REWRITTEN 2026-07-01, adopting the architecture test_rl_ppo.py already
specified. Superseded: the earlier PPORouter, which operated per-caller
(choose_action(caller, node)) -- that was the "differential" layer, now
correctly separated into Simulator's own deterministic graph traversal
(see Sim/Simulator.py). This engine only ever sees AGGREGATE queue load,
never an individual caller -- the "transmission" layer from the
transmission/differential discussion. Not called by Simulator.step().

RESOLVED 2026-07-02 (was an open question, now settled): higher load ->
higher probability is CORRECT, but not for either reason originally
guessed (traffic routing, or capacity/staffing allocation). Neither applies:
Simulator already routes callers by their own intent (this engine was never
in that path), and StaffingRLEngine was removed entirely -- Iceberg's
objective ends at the ACD door, staffing decisions live past it and require
data (AHT, shrinkage, answered-vs-offered) Iceberg can never see.

The actual answer: `probs` means "where should friction-finding ATTENTION go
first," not routing and not staffing. `load` is meant to represent STRESS
CONCENTRATION on a path -- built from LatentPayload's frustration/trust-decay/
volatility rolled up across everyone who took that path -- not occupancy or
headcount. Under that definition, higher concentration correctly getting
higher probability isn't backwards, it's triage.

WHAT'S STILL NOT DONE, separate from the (now-settled) direction question:
the rollup itself -- turning many callers' LatentPayload readings into one
per-queue stress-concentration number -- doesn't exist yet. That's the
aggregation layer ("C" from the transmission/differential discussion), still
unbuilt. `queues` here still just takes whatever "load" value it's handed;
nothing yet guarantees that value is actually stress concentration and not
something else. The composite formula itself (how much weight frustration
gets vs. trust-decay vs. volatility) is also still an open modeling choice,
not decided here -- flagged for [REDACTED_NAME]'s input, not guessed at.

Governance Notes:
- lr/gamma/eps_clip are config only, stored, not "trained" -- this is
  deterministic policy INFERENCE over fixed, seeded weights, same honest
  distinction Opus's review flagged for the pre-fork version.
- Weights are a pure function of sorted(queue names) -- NOT Python's
  built-in hash(), which is randomized per interpreter session and would
  break cross-session replay (the exact landmine flagged earlier today).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any
import numpy as np


@dataclass
class PPOEngine:
    lr: float
    gamma: float
    eps_clip: float
    seed: int = 815
    _weight_cache: Dict[int, np.ndarray] = field(default_factory=dict, compare=False, repr=False)

    def _weights(self, names: list) -> np.ndarray:
        # Fixed 2026-07-01: weights are a pure function of self.seed and
        # len(names) only (never the actual queue name strings), so they
        # were being recomputed identically on every call. Cached by count --
        # verified this doesn't change any output, since two different sets
        # of queues with the same count already produced identical base
        # weight vectors before caching, just recomputed wastefully.
        n = len(names)
        if n not in self._weight_cache:
            rng = np.random.RandomState(self.seed)
            self._weight_cache[n] = rng.randn(n)
        return self._weight_cache[n]

    def compute_action(self, queues: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """
        Deterministic action distribution over queues, driven by relative
        load. See RESOLVED note in the module docstring -- higher-load
        (stress-concentration) queues correctly get higher probability, as
        a triage signal, not a routing or staffing decision.

        Scale note: loads (tested at 0.0-1.0) dominate the 0.01-scaled prior
        by construction, but if real loads cluster near zero, the prior could
        dominate unexpectedly -- same "unvalidated constant" category as the
        rest of this codebase's tunables, not fixed without real data.
        """
        names = sorted(queues.keys())
        if not names:
            # No step-kind nodes are occupied this tick -- every remaining
            # caller is standing at a marker, past the door, about to be
            # swept. There is nothing to triage, and a softmax over zero
            # candidates has no meaning. Empty in, empty out.
            # RECONSTRUCTION FIX 2026-09-11: unreachable before Correction 1,
            # because a queue-occupancy aggregator always emitted a key per
            # queue. Node-kind filtering in IntegrationLoop Phase B made the
            # empty case real. See PROVENANCE.md.
            return {"probs": {}}
        loads = np.array([float(queues[n].get("load", 0.0)) for n in names])
        base = self._weights(names)

        logits = base * 0.01 + loads  # small deterministic prior + dominant load signal
        exp = np.exp(logits - np.max(logits))  # numerically stable softmax
        probs = exp / exp.sum()

        return {"probs": {n: float(p) for n, p in zip(names, probs)}}


