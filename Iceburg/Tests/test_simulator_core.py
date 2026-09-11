"""Simulator: deterministic traversal and Correction 2/4 boundaries."""
import pytest

from CallerState import CallerState
from Simulator import Simulator
from Telemetry import TelemetryKernel


def test_step_follows_the_declared_journey(simulator, caller_factory, graph):
    c = caller_factory("c0", "balance")
    journey = graph.journeys["balance"]
    for expected in journey[1:]:
        if graph.kind_of(c.route[-1]) != "step":
            break
        simulator.step(c)
        assert c.route[-1] == expected


def test_route_records_full_history(simulator, caller_factory):
    c = caller_factory("c0", "billing")
    while simulator.graph.kind_of(c.route[-1]) == "step":
        simulator.step(c)
    assert c.route[0] == "root"
    assert len(c.route) == len(set(c.route))


def test_stepping_past_a_marker_is_refused(simulator, caller_factory):
    """Correction 2: past the door, no step, no latent evolution, no data."""
    c = caller_factory("c0", "complaint")
    while simulator.graph.kind_of(c.route[-1]) == "step":
        simulator.step(c)
    with pytest.raises(RuntimeError, match="past the"):
        simulator.step(c)


def test_unrouteable_intent_raises_rather_than_guessing(simulator, caller_factory):
    c = caller_factory("c0", "billing")
    simulator.step(c)                       # root -> intent_menu (single edge)
    c.intent = "no_such_intent"
    # intent_menu is the branch point: with no declared journey there is no
    # deterministic successor, and refusing beats silently picking one.
    with pytest.raises(RuntimeError, match="no journey"):
        simulator.step(c)


def test_max_steps_is_enforced_per_caller(graph, telemetry, caller_factory):
    sim = Simulator(graph=graph, telemetry=telemetry, max_steps=2)
    c = caller_factory("c0", "balance")
    sim.step(c)
    sim.step(c)
    with pytest.raises(RuntimeError, match="max_steps"):
        sim.step(c)


def test_max_steps_is_not_a_simulator_wide_counter(graph, telemetry, caller_factory):
    """Three different callers stepped through one Simulator must not share
    a budget."""
    sim = Simulator(graph=graph, telemetry=telemetry, max_steps=3)
    for cid in ("a", "b", "c"):
        c = caller_factory(cid, "billing")
        sim.step(c)
        sim.step(c)


def test_simulator_rejects_a_non_graph(telemetry):
    with pytest.raises(ValueError, match="nodes"):
        Simulator(graph=object(), telemetry=telemetry)


def test_divert_takes_the_unique_handoff_escape(simulator, caller_factory):
    c = caller_factory("c0", "balance")
    simulator.step(c)                       # root -> intent_menu
    simulator.step(c)                       # -> balance::auth
    r = simulator.divert(c)
    assert r["diverted"] is True
    assert simulator.graph.kind_of(c.route[-1]) == "handoff"


def test_divert_without_a_deterministic_escape_raises(simulator, caller_factory):
    c = caller_factory("c0", "billing")
    with pytest.raises(RuntimeError, match="no deterministic escape"):
        simulator.divert(c)                 # at root, no handoff neighbor


def test_termination_self_service_is_success(simulator, caller_factory):
    """Correction 4: both doors are first-class success points."""
    c = caller_factory("c0", "balance")
    while simulator.graph.kind_of(c.route[-1]) == "step":
        simulator.step(c)
    rec = simulator.record_termination(c)
    assert rec["outcome"] == "success"
    assert rec["outcome_path"] == "self_service"


def test_termination_handoff_is_success(simulator, caller_factory):
    c = caller_factory("c0", "billing")
    while simulator.graph.kind_of(c.route[-1]) == "step":
        simulator.step(c)
    rec = simulator.record_termination(c)
    assert rec["outcome"] == "success"
    assert rec["outcome_path"] == "handoff"


def test_termination_before_any_marker_is_abandonment(simulator, caller_factory):
    c = caller_factory("c0", "balance")
    simulator.step(c)                       # still mid-journey
    rec = simulator.record_termination(c)
    assert rec["outcome"] == "abandonment"
    assert rec["outcome_path"] is None
    assert rec["marker_node"] is None


def test_classification_uses_no_threshold(simulator, caller_factory):
    """peak_frustration is severity, never the classifier."""
    c = caller_factory("c0", "billing")
    while simulator.graph.kind_of(c.route[-1]) == "step":
        simulator.step(c)
    c.latent.peak_frustration = 1.0         # maximally distressed
    rec = simulator.record_termination(c)
    assert rec["outcome"] == "success"      # reached the door anyway
    assert rec["peak_frustration"] == pytest.approx(1.0)


def test_update_queue_is_gone():
    """Correction 1: deleted, not stubbed, not deprecated."""
    assert not hasattr(Simulator, "update_queue")


def test_identical_runs_produce_identical_ledgers(graph, caller_factory):
    hashes = []
    for _ in range(2):
        tel = TelemetryKernel()
        sim = Simulator(graph=graph, telemetry=tel)
        for cid in ("a", "b", "c"):
            c = CallerState.new(cid, intent="balance")
            while sim.graph.kind_of(c.route[-1]) == "step":
                sim.step(c)
            sim.record_termination(c)
        hashes.append((tel.structural_hash(), tel.content_hash()))
    assert hashes[0] == hashes[1]
