"""MARLEngine: per-node agents over the same aggregate signal."""
import pytest

from rl_marl import MARLEngine


def q(**loads):
    return {k: {"load": v, "peak": v, "breadth": v, "n": 1.0}
            for k, v in loads.items()}


@pytest.fixture
def marl():
    return MARLEngine(lr=3e-4, gamma=0.99, eps_clip=0.2)


def test_empty_input_is_empty(marl):
    assert marl.compute_action({}) == {"agents": {}, "probs": {}}


def test_one_agent_per_node(marl):
    out = marl.compute_action(q(a=0.1, b=0.2, c=0.3))
    assert set(out["agents"]) == {"a", "b", "c"}


def test_attention_sums_to_one(marl):
    out = marl.compute_action(q(a=0.1, b=0.7))
    assert sum(out["probs"].values()) == pytest.approx(1.0)


def test_severity_is_reported_per_agent(marl):
    out = marl.compute_action(q(a=0.2, b=0.8))
    assert out["agents"]["b"]["severity"] == pytest.approx(0.8)


def test_probs_view_matches_attention(marl):
    out = marl.compute_action(q(a=0.2, b=0.8))
    assert out["probs"] == {k: v["attention"] for k, v in out["agents"].items()}


def test_deterministic_across_instances():
    a = MARLEngine(lr=1.0, gamma=1.0, eps_clip=1.0)
    b = MARLEngine(lr=1.0, gamma=1.0, eps_clip=1.0)
    assert a.compute_action(q(x=0.3, y=0.6)) == b.compute_action(q(x=0.3, y=0.6))
