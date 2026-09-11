"""PathCongestion: Tier 3 aggregation over co-navigation, not occupancy."""
import pytest

from PathCongestion import (PEAK_WEIGHT, _caller_distress,
                            compute_path_congestion)


def snap(cid, frustration=0.0, **latent):
    lat = {"trust_baseline": 0.5, "trust_scalar": 0.5, "friction_count": 0,
           "volatility": 0.0, "memory_flag": 0.0}
    lat.update(latent)
    return {"caller_id": cid, "dynamic": {"frustration": frustration},
            "latent": lat}


def test_empty_input_is_empty_output():
    assert compute_path_congestion({}) == {}


def test_empty_node_is_fully_quiet():
    out = compute_path_congestion({"n": []})
    assert out["n"] == {"load": 0.0, "peak": 0.0, "breadth": 0.0, "n": 0.0}


def test_output_shape_is_preserved_for_the_engines():
    out = compute_path_congestion({"n": [snap("a", 0.4)]})
    assert set(out["n"]) == {"load", "peak", "breadth", "n"}


def test_snapshot_order_does_not_change_the_result():
    a, b = snap("a", 0.2), snap("b", 0.9)
    assert compute_path_congestion({"n": [a, b]}) == \
           compute_path_congestion({"n": [b, a]})


def test_load_is_bounded():
    out = compute_path_congestion(
        {"n": [snap(f"c{i}", 1.0, trust_scalar=0.0, friction_count=999,
                    volatility=1.0, memory_flag=1.0) for i in range(5)]})
    assert 0.0 <= out["n"]["load"] <= 1.0


def test_peak_dominates_breadth_by_design():
    """One badly-stuck caller among calm ones must still register."""
    many_calm = [snap(f"c{i}", 0.0) for i in range(9)]
    out = compute_path_congestion({"n": many_calm + [snap("x", 1.0)]})
    assert out["n"]["peak"] > out["n"]["breadth"]
    assert PEAK_WEIGHT > 0.5


def test_missing_latent_falls_back_to_raw_frustration():
    s = {"caller_id": "a", "dynamic": {"frustration": 0.7}, "latent": None}
    assert _caller_distress(s) == pytest.approx(0.7)


def test_n_counts_co_navigating_callers():
    out = compute_path_congestion({"n": [snap("a"), snap("b"), snap("c")]})
    assert out["n"]["n"] == 3.0
