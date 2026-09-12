"""IngestAdapter: mechanical translation of raw logs into friction stimuli."""
import pytest

import IngestAdapter as IA
from Build_Graph import build_graph


@pytest.fixture
def journeys(graph):
    return graph.journeys


@pytest.fixture
def call(graph, journeys):
    import random
    return IA.generate_synthetic_call(
        "C0001", journeys["balance"], random.Random(815), "clean")


def derive(graph, events, **kw):
    return IA.derive_stimuli(events, graph.resolution_nodes(),
                             graph.handoff_nodes(), **kw)


def test_population_is_deterministic_under_a_seed(journeys):
    a = IA.generate_population(journeys, 8, seed=815)
    b = IA.generate_population(journeys, 8, seed=815)
    assert a == b


def test_a_different_seed_gives_a_different_population(journeys):
    a = IA.generate_population(journeys, 8, seed=1)
    b = IA.generate_population(journeys, 8, seed=2)
    assert a != b


def test_log_opens_and_closes_a_call(call):
    assert call[0]["type"] == "call_start"
    assert call[-1]["type"] == "call_end"


def test_timestamps_are_monotone(call):
    ts = [e["timestamp"] for e in call]
    assert ts == sorted(ts)


def test_route_is_derived_from_menu_events(graph, call):
    d = derive(graph, call)
    assert d.route[0] == "root"
    assert len(d.stimuli_by_hop) == len(d.route)


def test_every_hop_carries_the_four_stimulus_fields(graph, call):
    d = derive(graph, call)
    for hop in d.stimuli_by_hop:
        assert {"friction_event", "actual_wait", "expected_wait",
                "resolved"} <= set(hop)


def test_a_clean_call_reaching_a_marker_is_hinted_success(graph, journeys):
    import random
    ev = IA.generate_synthetic_call("C1", journeys["balance"],
                                    random.Random(1), "clean")
    assert derive(graph, ev).final_outcome_hint == "success"


def test_a_hangup_before_any_marker_is_hinted_abandonment(graph, journeys):
    import random
    ev = IA.generate_synthetic_call("C2", journeys["balance"],
                                    random.Random(3), "hangup")
    assert derive(graph, ev).final_outcome_hint == "abandonment"


def test_a_revisit_registers_friction(graph, journeys):
    """Backtracking to a node already in this call's route is derivable from
    (timestamp, node) alone -- no modeling judgment."""
    import random
    ev = IA.generate_synthetic_call("C3", journeys["balance"],
                                    random.Random(5), "revisit")
    d = derive(graph, ev)
    assert any(h["friction_event"] for h in d.stimuli_by_hop)


def test_an_overrun_registers_friction(graph, journeys):
    import random
    ev = IA.generate_synthetic_call("C4", journeys["balance"],
                                    random.Random(7), "overrun")
    d = derive(graph, ev)
    assert any(h["friction_event"] for h in d.stimuli_by_hop)


def test_derivation_is_pure(graph, call):
    """Same log in, same stimuli out, every time."""
    assert derive(graph, call) == derive(graph, call)


def test_per_node_expected_wait_overrides_the_scalar(graph, call):
    d = derive(graph, call, expected_wait_by_node={"root": 999.0})
    assert d.stimuli_by_hop[0]["expected_wait"] == pytest.approx(999.0)
