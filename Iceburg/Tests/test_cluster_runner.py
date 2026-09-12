"""ClusterRunner: sharding must not disturb determinism."""
import pytest

from CallerState import CallerState
from IntegrationLoop import IntegrationLoop
from Simulator import Simulator
from Telemetry import TelemetryKernel
from cluster_runner import ClusterRunner
from rl_ppo import PPOEngine


def pop(n=12):
    intents = ["balance", "billing", "tech", "complaint"]
    return [CallerState.new(f"c{i:02d}", intent=intents[i % len(intents)])
            for i in range(n)]


def factory(graph):
    def _make(_idx):
        tel = TelemetryKernel()
        return IntegrationLoop(
            simulator=Simulator(graph=graph, telemetry=tel),
            engine=PPOEngine(lr=3e-4, gamma=0.99, eps_clip=0.2),
            telemetry=tel)
    return _make


def test_worker_count_must_be_positive():
    with pytest.raises(ValueError, match="workers"):
        ClusterRunner(workers=0)


def test_select_worker_is_stable_across_sessions():
    """Pure function of caller_id, never Python's randomized hash()."""
    r = ClusterRunner(workers=4)
    assert r.select_worker("c07") == r.select_worker("c07")
    assert 0 <= r.select_worker("anything") < 4


def test_every_caller_is_assigned_exactly_once():
    r = ClusterRunner(workers=3)
    shards = r.shard(pop())
    assigned = [c.caller_id for s in shards.values() for c in s]
    assert sorted(assigned) == sorted(c.caller_id for c in pop())


def test_shards_are_ordered_by_caller_id():
    r = ClusterRunner(workers=3)
    for shard in r.shard(pop()).values():
        ids = [c.caller_id for c in shard]
        assert ids == sorted(ids)


def test_total_terminations_are_invariant_to_worker_count(graph):
    totals = []
    for workers in (1, 2, 4, 7):
        tel = TelemetryKernel()
        r = ClusterRunner(telemetry=tel, workers=workers)
        totals.append(r.run(pop(), factory(graph))["terminated"])
    assert len(set(totals)) == 1
    assert totals[0] == len(pop())


def test_empty_shards_are_reported_not_skipped(graph):
    r = ClusterRunner(workers=20)
    summary = r.run(pop(4), factory(graph))
    assert len(summary["per_worker"]) == 20


def test_cluster_summary_is_recorded(graph):
    tel = TelemetryKernel()
    ClusterRunner(telemetry=tel, workers=2).run(pop(), factory(graph))
    assert tel.events_of("cluster_summary")
