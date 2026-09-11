"""IntegrationLoop: the only place the three tiers meet."""
import pytest

from CallerState import CallerState
from IntegrationLoop import IntegrationLoop
from Simulator import Simulator
from Telemetry import TelemetryKernel
from rl_ppo import PPOEngine


@pytest.fixture
def loop(simulator, engine, telemetry):
    return IntegrationLoop(simulator=simulator, engine=engine,
                           telemetry=telemetry)


def pop(*specs):
    return [CallerState.new(cid, intent=intent) for cid, intent in specs]


def test_every_caller_terminates(loop):
    res = loop.run(pop(("a", "balance"), ("b", "billing"), ("c", "complaint")))
    assert res["terminated"] == 3
    assert res["ticks"] > 0


def test_duplicate_caller_ids_are_refused(loop):
    with pytest.raises(ValueError, match="duplicate caller_id"):
        loop.run(pop(("a", "billing"), ("a", "tech")))


def test_intents_without_journeys_are_refused(loop):
    c = CallerState.new("a", intent="teleportation")
    with pytest.raises(ValueError, match="without journeys"):
        loop.run([c])


def test_loop_start_records_the_graph_for_audit(loop, telemetry):
    """The marker set and journey spec must be reconstructable from the
    ledger alone -- an audit cannot depend on the code still existing in the
    shape it had at run time."""
    loop.run(pop(("a", "billing")))
    start = telemetry.events_of("loop_start")[0]["payload"]
    assert "journeys" in start["graph"]
    assert start["graph"]["handoff_nodes"]


def test_markers_never_aggregate(loop, telemetry):
    """Correction 2: callers past the door contribute no congestion data."""
    loop.run(pop(("a", "balance"), ("b", "complaint")))
    markers = set(loop.simulator.graph.marker_nodes())
    for e in telemetry.events_of("tick_summary"):
        assert not (set(e["payload"]["path_congestion"]) & markers)


def test_a_hangup_terminates_the_caller(simulator, engine, telemetry):
    lp = IntegrationLoop(simulator=simulator, engine=engine,
                         telemetry=telemetry, hangups={(1, "a")})
    lp.run(pop(("a", "balance")))
    rec = telemetry.events_of("termination")[0]["payload"]
    assert rec["outcome"] == "abandonment"


def test_hangup_takes_precedence_over_diversion(simulator, engine, telemetry):
    """The caller's act preempts the system's."""
    lp = IntegrationLoop(simulator=simulator, engine=engine, telemetry=telemetry,
                         hangups={(1, "a")}, diversions={(1, "a")})
    lp.run(pop(("a", "balance")))
    rec = telemetry.events_of("termination")[0]["payload"]
    assert rec["outcome"] == "abandonment"


def test_diversion_lands_the_caller_at_a_handoff(simulator, engine, telemetry):
    lp = IntegrationLoop(simulator=simulator, engine=engine, telemetry=telemetry,
                         diversions={(2, "a")})
    lp.run(pop(("a", "balance")))
    rec = telemetry.events_of("termination")[0]["payload"]
    assert rec["outcome"] == "success"
    assert rec["outcome_path"] == "handoff"


def test_stimuli_are_applied_at_the_declared_tick(simulator, engine, telemetry):
    lp = IntegrationLoop(simulator=simulator, engine=engine, telemetry=telemetry,
                         stimuli={(2, "a"): {"friction_event": 1}})
    lp.run(pop(("a", "balance")))
    rec = telemetry.events_of("termination")[0]["payload"]
    assert rec["peak_frustration"] > 0.0


def test_max_ticks_is_enforced(simulator, engine, telemetry):
    lp = IntegrationLoop(simulator=simulator, engine=engine,
                         telemetry=telemetry, max_ticks=1)
    with pytest.raises(RuntimeError, match="max_ticks"):
        lp.run(pop(("a", "balance")))


def test_run_is_reproducible(graph):
    results = []
    for _ in range(2):
        tel = TelemetryKernel()
        lp = IntegrationLoop(
            simulator=Simulator(graph=graph, telemetry=tel),
            engine=PPOEngine(lr=3e-4, gamma=0.99, eps_clip=0.2),
            telemetry=tel,
            stimuli={(1, "b"): {"friction_event": 2}},
            diversions={(2, "c")},
        )
        results.append(lp.run(pop(("a", "balance"), ("b", "billing"),
                                  ("c", "tech"), ("d", "complaint"))))
    assert results[0] == results[1]


def test_deeper_self_service_costs_more_ticks(loop):
    """Correction 3: depth is the lever. 'If the IVR has the balance 5 menus
    deep, THAT is why Iceberg exists.'"""
    res = loop.run(pop(("deep", "balance")))
    deep_ticks = res["ticks"]

    tel = TelemetryKernel()
    sim = Simulator(graph=loop.simulator.graph, telemetry=tel)
    shallow = IntegrationLoop(
        simulator=sim, engine=PPOEngine(lr=3e-4, gamma=0.99, eps_clip=0.2),
        telemetry=tel)
    assert shallow.run(pop(("shallow", "complaint")))["ticks"] < deep_ticks
