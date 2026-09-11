"""
calibrate_expected_wait.py -- the deep dive.

Reframe: the earlier sweeps asked "what threshold makes cohort frustration
look reasonable?" -- unanswerable, no ground truth for "reasonable." The
right question, given Iceberg's mantra (reduce the friction that causes
people to LEAVE): which expected_wait policy makes the engine's friction
signal best SEPARATE callers who abandon from callers who complete, using
only signal accrued before termination?

That is measurable -- if abandonment has a cause. So this cohort is
behaviorally coupled: each caller draws a latent patience tolerance; holds
accumulate; when cumulative experienced wait exceeds tolerance, the caller
(usually) hangs up. Plus two confounders that keep the problem honest:
  - patient long-waiters: high-tolerance callers who complete despite waits
  - random abandoners: a small per-hop hazard, wait-innocent ("life happens")

Policies evaluated (the sensor changes, the world stays fixed):
  - flat constants (the original sweep family)
  - per-node empirical percentiles of observed holds (OBSERVABLE in real logs)
  - oracle remaining-budget (uses ground-truth tolerance -- UNOBSERVABLE,
    included only as a measurement ceiling)

Everything runs through the REAL Simulator/IntegrationLoop/PPOEngine.
"""
import sys, pathlib, random, math, statistics
from collections import defaultdict

_REPO = pathlib.Path(__file__).parent.parent.parent  # adjust as needed for your structure
sys.path.insert(0, str(_REPO))
for _sub in ("Latent", "Domain", "Sim", "Model", "SDK", "API", "Engines"):
    sys.path.insert(0, str(_REPO / _sub))
sys.path.insert(0, str(_REPO / "Aggregation"))
sys.path.insert(0, str(_REPO / "Loop"))

import Build_Graph as bg
import CallerState as cs
import Telemetry as tel
import Simulator as simmod
from rl_ppo import PPOEngine
from IntegrationLoop import IntegrationLoop
from IngestAdapter import derive_stimuli

graph = bg.build_graph()
RESOLUTION = graph.resolution_nodes()
HANDOFF = graph.handoff_nodes()

# ---------------------------------------------------------------------------
# Behavioral cohort
# ---------------------------------------------------------------------------

def hold_params(node):
    """(probability of a hold at this node, lognormal mu, lognormal sigma).
    Markers (resolution/handoff) are instants -- no holds, by architecture."""
    if node in RESOLUTION or node in HANDOFF:
        return None
    if node.endswith("::auth"):
        return (0.70, math.log(22.0), 0.9)   # auth/lookup: frequent, heavy tail
    if "::menu_" in node:
        return (0.30, math.log(15.0), 0.6)
    if node == "intent_menu":
        return (0.20, math.log(12.0), 0.6)
    return (0.25, math.log(15.0), 0.6)

def draw_tolerance(rng):
    r = rng.random()
    if r < 0.35:  return rng.lognormvariate(math.log(35.0), 0.4), "low"
    if r < 0.80:  return rng.lognormvariate(math.log(75.0), 0.4), "mid"
    return rng.lognormvariate(math.log(180.0), 0.4), "high"

RANDOM_HAZARD = 0.02       # per non-marker hop, wait-innocent abandonment
ABANDON_PROB_OVER_TOL = 0.9

def generate_behavioral_call(call_id, intent, rng):
    journey = graph.journeys[intent]
    hops = journey[1:]                      # skip root: hop j <-> tick j
    tolerance, band = draw_tolerance(rng)
    t = 0.0
    events = [{"call_id": call_id, "type": "call_start", "timestamp": t}]
    cum_wait = 0.0
    abandoned, cause, abandon_hop = False, None, None
    per_hop_cum_before = []                 # ground truth for the oracle

    for j, node in enumerate(hops):
        t += rng.uniform(3.0, 6.0)          # net transit, always under dwell gate
        events.append({"call_id": call_id, "type": "menu_reached",
                        "node": node, "timestamp": t})
        per_hop_cum_before.append(cum_wait)
        hp = hold_params(node)
        if hp:
            p, mu, sg = hp
            if rng.random() < p:
                hold = rng.lognormvariate(mu, sg)
                events.append({"call_id": call_id, "type": "hold_start", "timestamp": t})
                t += hold
                events.append({"call_id": call_id, "type": "hold_end", "timestamp": t})
                cum_wait += hold
        is_marker = (j == len(hops) - 1)
        if not is_marker:
            if cum_wait > tolerance and rng.random() < ABANDON_PROB_OVER_TOL:
                abandoned, cause, abandon_hop = True, "wait", j
                break
            if rng.random() < RANDOM_HAZARD:
                abandoned, cause, abandon_hop = True, "random", j
                break

    events.append({"call_id": call_id, "type": "call_end", "timestamp": t,
                    "disposition": "hangup" if abandoned else "completed"})
    return {"call_id": call_id, "intent": intent, "events": events,
            "abandoned": abandoned, "cause": cause, "abandon_hop": abandon_hop,
            "tolerance": tolerance, "band": band, "cum_wait": cum_wait,
            "cum_before": per_hop_cum_before}

# ---------------------------------------------------------------------------
# Build the fixed world once
# ---------------------------------------------------------------------------
N = 1000
rng = random.Random(815)
intents = list(graph.journeys.keys())
cohort = [generate_behavioral_call(f"C{i:04d}", intents[i % len(intents)], rng)
          for i in range(N)]

n_abandoned = sum(c["abandoned"] for c in cohort)
n_wait = sum(1 for c in cohort if c["cause"] == "wait")
n_random = sum(1 for c in cohort if c["cause"] == "random")
long_wait_completers = sum(1 for c in cohort
                            if not c["abandoned"] and c["cum_wait"] > 60.0)

print("=== COHORT GROUND TRUTH (fixed across all policies) ===")
print(f"callers: {N}   abandoned: {n_abandoned} ({n_abandoned/N:.1%})"
      f"   wait-caused: {n_wait}   random ('life happens'): {n_random}")
print(f"confounders: {long_wait_completers} completers waited >60s total"
      f" (patient long-waiters)")
by_band = defaultdict(lambda: [0, 0])
for c in cohort:
    by_band[c["band"]][0] += 1
    by_band[c["band"]][1] += c["abandoned"]
for band in ("low", "mid", "high"):
    tot, ab = by_band[band]
    print(f"  {band:4s} tolerance band: {tot} callers, {ab/tot:.1%} abandoned")

# Observable per-node hold distribution (what real logs would show)
node_holds = defaultdict(list)
for c in cohort:
    evs = c["events"]
    current_node = None
    open_start = None
    for e in evs:
        if e["type"] == "menu_reached":
            current_node = e["node"]
        elif e["type"] == "hold_start":
            open_start = e["timestamp"]
        elif e["type"] == "hold_end" and open_start is not None:
            node_holds[current_node].append(e["timestamp"] - open_start)
            open_start = None
all_holds = [h for v in node_holds.values() for h in v]

def pct(xs, q):
    ss = sorted(xs)
    k = max(0, min(len(ss) - 1, int(round(q / 100.0 * (len(ss) - 1)))))
    return ss[k]

global_median = pct(all_holds, 50)
print(f"\nobserved holds: {len(all_holds)} total; global median {global_median:.1f}s")
for node in sorted(node_holds):
    v = node_holds[node]
    print(f"  {node:22s} n={len(v):4d}  p50={pct(v,50):6.1f}s"
          f"  p75={pct(v,75):6.1f}s  p90={pct(v,90):6.1f}s")

# ---------------------------------------------------------------------------
# Policy evaluation through the REAL engine
# ---------------------------------------------------------------------------

def run_policy(name, by_node=None, scalar=None, oracle=False):
    telemetry = tel.TelemetryKernel()
    sim = simmod.Simulator(graph, telemetry, max_steps=50)
    engine = PPOEngine(lr=0.0003, gamma=0.99, eps_clip=0.2)

    callers, stimuli, hangups = [], {}, set()
    for c in cohort:
        derived = derive_stimuli(
            c["events"], RESOLUTION, HANDOFF,
            dwell_anomaly_seconds=8.0,
            expected_wait_seconds=(scalar if scalar is not None else global_median),
            expected_wait_by_node=by_node,
        )
        if oracle:  # remaining patience budget -- ground truth, ceiling only
            for j, hop in enumerate(derived.stimuli_by_hop):
                remaining = c["tolerance"] - c["cum_before"][j]
                hop["expected_wait"] = max(0.5, remaining)
        caller = cs.CallerState.new(caller_id=c["call_id"], intent=c["intent"])
        callers.append(caller)
        for tick, hop in enumerate(derived.stimuli_by_hop):
            stimuli[(tick, c["call_id"])] = {
                k: hop[k] for k in
                ("friction_event", "actual_wait", "expected_wait", "resolved")}
        if c["abandoned"]:
            hangups.add((c["abandon_hop"] + 1, c["call_id"]))

    loop = IntegrationLoop(simulator=sim, engine=engine, telemetry=telemetry,
                            stimuli=stimuli, hangups=hangups)
    result = loop.run(callers)
    assert result["terminated"] == N, f"{name}: {result['terminated']} != {N}"

    by_id = {c.caller_id: c for c in callers}
    pos, neg = [], []          # peak_frustration: the DESIGNED pre-relief signal
    hit_ab = flag_comp = 0     # gate-level (pre-relief): any hop actual>expected
    n_ab = n_comp = 0
    for c in cohort:
        caller = by_id[c["call_id"]]
        peak = caller.latent.peak_frustration
        # Gate-level overrun check straight from the stimuli this policy
        # produced -- NOT from post-relief friction_count residue, which the
        # engine deliberately decays on resolution ("earn back tolerance").
        any_overrun = any(
            stimuli[(t, c["call_id"])]["actual_wait"]
            > stimuli[(t, c["call_id"])]["expected_wait"]
            for t in range(len(c["cum_before"]))
            if (t, c["call_id"]) in stimuli
        )
        if c["abandoned"]:
            pos.append(peak); n_ab += 1; hit_ab += any_overrun
        else:
            neg.append(peak); n_comp += 1; flag_comp += any_overrun

    def auc(P, Ng):
        if not P or not Ng:
            return float("nan")
        wins = ties = 0
        for p in P:
            for n_ in Ng:
                if p > n_: wins += 1
                elif p == n_: ties += 1
        return (wins + 0.5 * ties) / (len(P) * len(Ng))

    return {
        "name": name,
        "auc_peak": auc(pos, neg),
        "abandoner_hit": hit_ab / n_ab,
        "completer_flag": flag_comp / n_comp,
        "gap": statistics.mean(pos) - statistics.mean(neg),
    }

policies = []
for v in (15, 20, 30, 45, 60, 90, 120):
    policies.append((f"flat_{v}s", None, float(v), False))
for q in (50, 75, 90):
    by_node = {n: pct(v, q) for n, v in node_holds.items()}
    policies.append((f"node_p{q}", by_node, None, False))
policies.append(("oracle_budget", None, None, True))

print("\n=== POLICY EVALUATION (peak_frustration = designed pre-relief signal) ===")
print(f"{'policy':>14} {'AUC(peak)':>10} {'abandoner_hit':>14}"
      f" {'completer_flag':>15} {'peak_gap':>9}")
for name, by_node, scalar, oracle in policies:
    r = run_policy(name, by_node, scalar, oracle)
    print(f"{r['name']:>14} {r['auc_peak']:>10.3f}"
          f" {r['abandoner_hit']:>14.1%} {r['completer_flag']:>15.1%}"
          f" {r['gap']:>9.4f}")
