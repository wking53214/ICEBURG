"""
conftest.py
-----------

Path wiring and shared fixtures.

The original repository used per-module sys.path.insert() calls rather than a
package (Domain/CallerState.py does this to reach Latent/LatentPayload.py).
That style is preserved so the recovered modules run exactly as recovered;
this file makes every module directory importable so tests can import them by
bare module name the same way the engine does.
"""
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
for _d in ("Latent", "Domain", "Model", "Aggregation", "Engines",
           "Sim", "Loop", "SDK", "Training/Modules"):
    p = str(ROOT / _d)
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture
def graph():
    from Build_Graph import build_graph
    return build_graph()


@pytest.fixture
def telemetry():
    from Telemetry import TelemetryKernel
    return TelemetryKernel()


@pytest.fixture
def simulator(graph, telemetry):
    from Simulator import Simulator
    return Simulator(graph=graph, telemetry=telemetry)


@pytest.fixture
def engine():
    from rl_ppo import PPOEngine
    return PPOEngine(lr=3e-4, gamma=0.99, eps_clip=0.2)


@pytest.fixture
def caller_factory():
    from CallerState import CallerState

    def _make(caller_id="c0", intent="billing"):
        return CallerState.new(caller_id, intent=intent)
    return _make
