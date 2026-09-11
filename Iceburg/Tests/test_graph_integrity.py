"""Graph topology invariants -- Corrections 1, 2 and 3."""
import pytest

from Build_Graph import (GraphBuilder, NODE_HANDOFF, NODE_RESOLUTION,
                         NODE_STEP, build_graph)


def test_no_queue_nodes_anywhere(graph):
    """Correction 1: a queue does not exist in an IVR, only directionality."""
    assert not [n for n in graph.nodes if n.endswith("_queue")]


def test_markers_are_terminal(graph):
    """Correction 2/3: markers are instants, not places anyone dwells."""
    for name in graph.marker_nodes():
        assert graph.nodes[name].neighbors == []


def test_every_journey_ends_at_a_marker(graph):
    for intent, path in graph.journeys.items():
        assert graph.kind_of(path[-1]) in (NODE_RESOLUTION, NODE_HANDOFF), intent


def test_every_journey_starts_at_root(graph):
    for intent, path in graph.journeys.items():
        assert path[0] == "root", intent


def test_no_journey_passes_through_a_marker(graph):
    for intent, path in graph.journeys.items():
        for node in path[:-1]:
            assert graph.kind_of(node) == NODE_STEP, (intent, node)


def test_self_service_has_real_depth(graph):
    """Correction 3: 'if the IVR has the balance 5 menus deep, THAT is why
    Iceberg exists'. Depth is configuration, because depth IS the lever."""
    steps = [n for n in graph.journeys["balance"] if graph.kind_of(n) == NODE_STEP]
    assert len(steps) >= 5


def test_self_service_and_handoff_are_both_represented(graph):
    assert graph.resolution_nodes()
    assert graph.handoff_nodes()


def test_every_step_has_at_most_one_divert_escape(graph):
    for name, node in graph.nodes.items():
        if graph.kind_of(name) != NODE_STEP:
            continue
        declared = {nxt for succ in graph._journey_next.values()
                    for src, nxt in succ.items() if src == name}
        escapes = [nb for nb in node.neighbors
                   if graph.kind_of(nb) == NODE_HANDOFF and nb not in declared]
        assert len(escapes) <= 1, name


def test_validate_rejects_a_non_terminal_marker():
    b = GraphBuilder()
    b.handoff("billing", ["auth"])
    g = b.build()
    hof = next(iter(g.handoff_nodes()))
    g.nodes[hof].neighbors = ["root"]
    with pytest.raises(ValueError, match="must be terminal"):
        g.validate()


def test_validate_rejects_a_dangling_edge():
    b = GraphBuilder()
    b.handoff("billing", ["auth"])
    g = b.build()
    g.nodes["root"].neighbors = ["nowhere"]
    with pytest.raises(ValueError, match="Missing"):
        g.validate()


def test_build_is_deterministic():
    a, b = build_graph(), build_graph()
    assert a.to_dict() == b.to_dict()


def test_journey_next_is_o1_and_total(graph):
    for intent, path in graph.journeys.items():
        for src, dst in zip(path, path[1:]):
            assert graph.journey_next(intent, src) == dst
        assert graph.journey_next(intent, path[-1]) is None
