"""LatentPayload: the friction engine. Determinism, clamping, and the
anti-gaming properties the substrate exists to guarantee."""
import pytest

from CallerState import DynamicState
from LatentPayload import LatentPayload


def dyn(**kw):
    return DynamicState(**kw)


def test_trust_baseline_anchors_at_construction():
    p = LatentPayload(trust_scalar=0.42)
    assert p.trust_baseline == pytest.approx(0.42)


def test_quiet_step_moves_nothing():
    """Event-driven, not flat-drift: the old version pinned memory to 1.0 by
    step ~100 regardless of what happened."""
    p = LatentPayload()
    before = p.to_dict()
    p.update_after_step(dyn())
    after = p.to_dict()
    for k in ("trust_scalar", "volatility", "memory_flag", "friction_count"):
        assert before[k] == after[k], k
    assert after["step_index"] == before["step_index"] + 1


def test_friction_raises_frustration_and_costs_trust():
    p = LatentPayload()
    d = dyn(friction_event=1)
    p.update_after_step(d)
    assert d.frustration > 0.0
    assert p.friction_count == 1
    assert p.trust_scalar < 0.5


def test_friction_accrual_grows_past_tolerance():
    """The first adverse event costs less than the fifth: below _TOLERANCE the
    accrual is flat, and past it each further event costs strictly more."""
    p = LatentPayload()
    deltas = []
    for _ in range(5):
        d = dyn(friction_event=1)
        p.update_after_step(d)
        deltas.append(d.frustration)
    assert deltas == sorted(deltas)
    assert deltas[-1] > deltas[0]
    # Accrual is linear in the overage past tolerance, by construction:
    # escalation_rate * (1 + over_tol) * (1 - patience).
    steps = [round(b - a, 12) for a, b in zip(deltas, deltas[1:])]
    assert len(set(steps)) == 1 and steps[0] > 0


def test_friction_count_is_capped():
    p = LatentPayload()
    for _ in range(100):
        p.update_after_step(dyn(friction_event=1))
    assert p.friction_count == p._FRICTION_CAP


def test_negative_friction_event_cannot_corrupt_the_count():
    p = LatentPayload()
    p.update_after_step(dyn(friction_event=-5))
    assert p.friction_count == 0


def test_memory_flag_never_decays():
    """memory_flag is the permanent record that friction occurred,
    independent of whether the call ultimately felt resolved."""
    p = LatentPayload()
    p.update_after_step(dyn(friction_event=1))
    marked = p.memory_flag
    assert marked > 0.0
    for _ in range(20):
        p.update_after_step(dyn(resolved=True))
    assert p.memory_flag >= marked


def test_friction_and_resolution_can_both_apply_in_one_step():
    """Verified case: caller misroutes once, then the SAME step reaches the
    correct agent. The old elif meant the friction branch always won and
    relief silently never fired."""
    p = LatentPayload()
    d = dyn(friction_event=1, resolved=True)
    p.update_after_step(d)
    # memory_flag is the permanent, un-relievable record that the hit landed.
    assert p.memory_flag > 0.0
    # Relief then applied ON TOP of it, rather than the friction branch
    # silently winning: this step's frustration is fully relieved and the
    # earned tolerance is handed back (_FRICTION_DECAY_PER_RELIEF).
    assert d.frustration == pytest.approx(0.0)
    assert p.friction_count == 0
    # And fix #9 holds: relief undid this step's trust damage but did not
    # lift trust above where it stood at the start of the step.
    assert p.trust_scalar == pytest.approx(LatentPayload().trust_scalar)


def test_relief_cannot_exceed_step_start_trust_when_friction_occurred():
    """Anti-gaming: a misroute-then-resolve step must not net HIGHER trust
    than a step where nothing happened at all -- that would reward
    manufacturing a small fixable stumble over running clean."""
    clean = LatentPayload()
    clean.update_after_step(dyn())

    rocky = LatentPayload()
    rocky.update_after_step(dyn(friction_event=1, resolved=True))

    assert rocky.trust_scalar <= clean.trust_scalar


def test_trust_never_leaves_the_unit_interval():
    p = LatentPayload()
    for i in range(200):
        p.update_after_step(dyn(friction_event=i % 3, resolved=bool(i % 2)))
        assert 0.0 <= p.trust_scalar <= 1.0
        assert 0.0 <= p.volatility <= 1.0
        assert 0.0 <= p.memory_flag <= 1.0


def test_peak_frustration_is_a_never_decaying_high_water_mark():
    """The caller who spiked to distress then got smoothed by relief before
    quitting is exactly the caller a final-value check misses."""
    p = LatentPayload()
    d = dyn()
    for _ in range(6):
        p.update_after_step(dyn(friction_event=2, frustration=d.frustration))
        d.frustration = min(1.0, d.frustration + 0.25)
    p.update_after_step(d)
    peak = p.peak_frustration
    assert peak > 0.0
    for _ in range(30):
        d.frustration = 0.0
        p.update_after_step(dyn(resolved=True))
    assert p.peak_frustration == peak


def test_reset_for_new_call_clears_per_call_state_only():
    p = LatentPayload()
    p.update_after_step(dyn(friction_event=1))
    p.memory_flag = 0.7
    trust = p.trust_scalar
    p.reset_for_new_call()
    assert p.friction_count == 0
    assert p.peak_frustration == 0.0
    assert p.trust_baseline == pytest.approx(trust)
    assert p.memory_flag == 0.7          # relationship state persists
    assert p.trust_scalar == pytest.approx(trust)


def test_step_index_is_monotone():
    p = LatentPayload()
    for i in range(1, 25):
        p.update_after_step(dyn())
        assert p.step_index == i


def test_perceived_wait_is_dilated_by_frustration():
    """A frustrated caller experiences the same clock time as longer."""
    calm, cross = LatentPayload(), LatentPayload()
    dc = dyn(actual_wait=150.0, frustration=0.0)
    dx = dyn(actual_wait=150.0, frustration=0.9)
    calm.update_after_step(dc)
    cross.update_after_step(dx)
    assert dx.perceived_wait > dc.perceived_wait


def test_tunables_are_excluded_from_the_serialized_surface():
    d = LatentPayload().to_dict()
    assert not [k for k in d if k.startswith("_")]


def test_hashes_are_deterministic_across_instances():
    a, b = LatentPayload(), LatentPayload()
    assert a.content_hash() == b.content_hash()
    assert a.structural_hash() == b.structural_hash()


def test_quiet_step_moves_structural_hash_but_not_content_hash():
    """Two explicitly labelled hashes, because 'the hash changed' has to mean
    something specific. structural_hash covers ALL state including
    step_index, so it moves on every step -- that is what replay equivalence
    needs. content_hash excludes step_index, so it moves only when something
    emotionally meaningful actually did."""
    p = LatentPayload()
    s0, c0 = p.structural_hash(), p.content_hash()
    p.update_after_step(dyn())                  # quiet step
    assert p.structural_hash() != s0            # a step elapsed
    assert p.content_hash() == c0               # nothing real happened
    p.update_after_step(dyn(friction_event=1))  # real step
    assert p.content_hash() != c0


def test_load_from_dict_preserves_int_and_none_types():
    """Previously ran _clamp() over everything: friction_count=5 silently
    became 1.0 and trust_baseline=None crashed outright."""
    p = LatentPayload()
    p.load_from_dict({"friction_count": 5, "step_index": 42,
                      "trust_baseline": None, "volatility": 1.7})
    assert p.friction_count == 5 and isinstance(p.friction_count, int)
    assert p.step_index == 42 and isinstance(p.step_index, int)
    assert p.trust_baseline is None
    assert p.volatility == pytest.approx(1.0)      # float clamping still bounds


def test_identical_inputs_produce_identical_trajectories():
    """Replay safety: identical payload inputs -> identical latent evolution."""
    script = [dict(friction_event=i % 3, resolved=bool(i % 4 == 0),
                   actual_wait=float(i), expected_wait=2.0) for i in range(40)]
    outs = []
    for _ in range(2):
        p = LatentPayload()
        for s in script:
            p.update_after_step(dyn(**s))
        outs.append(p.content_hash())
    assert outs[0] == outs[1]
