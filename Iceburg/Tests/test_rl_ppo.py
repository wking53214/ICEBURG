"""PPOEngine: deterministic triage inference over aggregate congestion."""
import pytest

from rl_ppo import PPOEngine


def q(**loads):
    return {k: {"load": v, "peak": v, "breadth": v, "n": 1.0}
            for k, v in loads.items()}


def test_empty_input_returns_an_empty_distribution(engine):
    """Every remaining caller is at a marker; there is nothing to triage."""
    assert engine.compute_action({}) == {"probs": {}}


def test_probabilities_sum_to_one(engine):
    probs = engine.compute_action(q(a=0.1, b=0.5, c=0.9))["probs"]
    assert sum(probs.values()) == pytest.approx(1.0)


def test_higher_load_gets_higher_probability(engine):
    probs = engine.compute_action(q(quiet=0.0, loud=0.9))["probs"]
    assert probs["loud"] > probs["quiet"]


def test_output_is_deterministic_across_instances():
    a = PPOEngine(lr=3e-4, gamma=0.99, eps_clip=0.2)
    b = PPOEngine(lr=3e-4, gamma=0.99, eps_clip=0.2)
    assert a.compute_action(q(x=0.3, y=0.6)) == b.compute_action(q(x=0.3, y=0.6))


def test_weights_do_not_depend_on_python_hash_randomization():
    """Weights are a pure function of seed and count, never hash() -- which is
    randomized per interpreter session and would break cross-session replay."""
    e = PPOEngine(lr=1.0, gamma=1.0, eps_clip=1.0)
    import numpy as np
    assert np.array_equal(e._weights(["a", "b"]), e._weights(["z", "y"]))


def test_a_different_seed_gives_a_different_prior():
    a = PPOEngine(lr=1.0, gamma=1.0, eps_clip=1.0, seed=1)
    b = PPOEngine(lr=1.0, gamma=1.0, eps_clip=1.0, seed=2)
    assert a.compute_action(q(x=0.0, y=0.0)) != b.compute_action(q(x=0.0, y=0.0))


def test_single_node_takes_all_the_attention(engine):
    probs = engine.compute_action(q(only=0.4))["probs"]
    assert probs == {"only": pytest.approx(1.0)}


def test_missing_load_key_defaults_to_zero(engine):
    probs = engine.compute_action({"a": {}, "b": {"load": 0.9}})["probs"]
    assert probs["b"] > probs["a"]
