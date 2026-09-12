#!/usr/bin/env python3
"""
run_worked_example.py

End-to-end demonstration of the recovered engine: build the graph, run a
mixed population through the integration loop, and print what Iceberg
actually concludes about each call.

    python3 run_worked_example.py
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent / "Iceburg"
for _d in ("Latent", "Domain", "Model", "Aggregation", "Engines",
           "Sim", "Loop", "SDK"):
    sys.path.insert(0, str(ROOT / _d))

from Build_Graph import build_graph          # noqa: E402
from CallerState import CallerState          # noqa: E402
from IntegrationLoop import IntegrationLoop  # noqa: E402
from Simulator import Simulator              # noqa: E402
from Telemetry import TelemetryKernel        # noqa: E402
from rl_ppo import PPOEngine                 # noqa: E402


def main() -> None:
    graph = build_graph()
    telemetry = TelemetryKernel()
    loop = IntegrationLoop(
        simulator=Simulator(graph=graph, telemetry=telemetry),
        engine=PPOEngine(lr=3e-4, gamma=0.99, eps_clip=0.2),
        telemetry=telemetry,
        # A rough tick: one caller takes friction, one gets 0-outed to a
        # human, one simply gives up.
        stimuli={(2, "c002"): {"friction_event": 2}},
        diversions={(3, "c003")},
        hangups={(4, "c004")},
    )

    population = [
        CallerState.new("c000", intent="balance"),     # 5-deep self-service
        CallerState.new("c001", intent="billing"),     # straight to handoff
        CallerState.new("c002", intent="balance"),     # hits friction
        CallerState.new("c003", intent="tech"),        # diverted to a human
        CallerState.new("c004", intent="balance"),     # abandons mid-journey
        CallerState.new("c005", intent="complaint"),   # no steps at all
    ]

    print(f"graph: {len(graph.nodes)} nodes, {len(graph.journeys)} journeys, "
          f"{len(graph.marker_nodes())} markers, 0 queues (Correction 1)\n")

    result = loop.run(population)

    print(f"{'caller':<8}{'intent':<12}{'outcome':<14}{'via':<14}"
          f"{'hops':>5}{'peak_frustration':>19}")
    print("-" * 72)
    for event in telemetry.events_of("termination"):
        r = event["payload"]
        print(f"{r['caller_id']:<8}{r['intent']:<12}{r['outcome']:<14}"
              f"{str(r['outcome_path'] or '-'):<14}{r['route_length']:>5}"
              f"{r['peak_frustration']:>19.4f}")

    print(f"\nticks: {result['ticks']}   terminated: {result['terminated']}")
    print(f"ledger: {len(telemetry)} events")
    print(f"ledger structural_hash: {result['ledger_hash']}")
    print("\nRe-running this file produces an identical hash. That is the "
          "whole point:\nthe ledger is the audit trail, and replay "
          "equivalence is what makes it one.")


if __name__ == "__main__":
    main()
