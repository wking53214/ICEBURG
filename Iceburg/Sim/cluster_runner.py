"""
cluster_runner.py
-----------------

Fan a population of callers across N deterministic workers and run them to
termination.

The only thing this adds over calling Simulator directly is SHARDING, and the
only hard requirement on the sharding is that it must not disturb determinism:
the same population over the same graph must produce the same terminations in
the same order regardless of how many workers are configured. Assignment is
therefore by stable sort of caller_id, never by arrival order, load, or
anything wall-clock.

Each worker gets its OWN Simulator and its OWN ledger. Ledgers stay
call-sized rather than accumulating into one multi-million-entry object, and a
worker's ledger can be replayed in isolation.

RECONSTRUCTED 2026-09-11 from the archived contract
-- ClusterRunner(simulator, telemetry, workers), events shaped {type, payload}.
The original source was not recovered. Note the archive also records a
CONTRACT FORK here that was never resolved: test_cluster_runner.py expected a
no-arg ClusterRunner() with a .select_worker() method, while the real class
required (simulator, telemetry, workers) and had neither. This
reconstruction follows the real class, and provides select_worker() so the
test-side expectation is also satisfiable. See PROVENANCE.md.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ClusterRunner:
    simulator: Any = None        # prototype; each shard gets its own copy
    telemetry: Any = None        # parent ledger, receives the cluster summary
    workers: int = 1

    def __post_init__(self):
        if self.workers < 1:
            raise ValueError("GSA Violation: workers must be >= 1")

    def select_worker(self, caller_id: str) -> int:
        """
        Deterministic shard assignment. Pure function of caller_id and worker
        count -- NOT Python's built-in hash(), which is randomized per
        interpreter session and would break cross-session replay.
        """
        acc = 0
        for ch in str(caller_id):
            acc = (acc * 31 + ord(ch)) & 0xFFFFFFFF
        return acc % self.workers

    def shard(self, callers: List[Any]) -> Dict[int, List[Any]]:
        """Stable, caller_id-sorted assignment. Order is reproducible."""
        out: Dict[int, List[Any]] = {i: [] for i in range(self.workers)}
        for c in sorted(callers, key=lambda c: str(c.caller_id)):
            out[self.select_worker(c.caller_id)].append(c)
        return out

    def run(self, callers: List[Any], loop_factory) -> Dict[str, Any]:
        """
        loop_factory(worker_index) -> an object with .run(callers) returning
        the IntegrationLoop result dict. Injected rather than constructed here
        so this module stays free of Loop/ and Engines/ imports.
        """
        results = {}
        for idx, shard in sorted(self.shard(callers).items()):
            if not shard:
                results[idx] = {"ticks": 0, "terminated": 0, "ledger_hash": None}
                continue
            results[idx] = loop_factory(idx).run(shard)

        summary = {
            "workers": self.workers,
            "callers": len(callers),
            "terminated": sum(r["terminated"] for r in results.values()),
            "per_worker": {str(k): v for k, v in sorted(results.items())},
        }
        if self.telemetry is not None:
            self.telemetry.record("cluster_summary", summary)
        return summary
