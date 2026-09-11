"""TelemetryKernel: append-only deterministic ledger."""
import pytest

from Telemetry import Telemetry, TelemetryKernel


def test_record_uses_the_type_key():
    t = TelemetryKernel()
    e = t.record("step", {"a": 1})
    assert e["type"] == "step"
    assert "event_type" not in e


def test_record_takes_exactly_two_arguments():
    t = TelemetryKernel()
    with pytest.raises(TypeError):
        t.record("step", {"a": 1}, {"b": 2})


def test_sequence_numbers_are_monotone():
    t = TelemetryKernel()
    for i in range(5):
        assert t.record("e", {})["seq"] == i


def test_payloads_are_copied_not_aliased():
    """CallerState.snapshot() returns self.posterior BY REFERENCE. Storing
    payloads by reference would let a later in-place mutation retroactively
    alter an already-recorded entry -- an append-only violation via aliasing,
    and a silent one."""
    t = TelemetryKernel()
    payload = {"posterior": {"billing": 0.25}}
    t.record("step", payload)
    payload["posterior"]["billing"] = 0.99
    assert t.entries[0]["payload"]["posterior"]["billing"] == 0.25


def test_to_list_does_not_expose_the_internal_entries():
    t = TelemetryKernel()
    t.record("step", {"x": 1})
    out = t.to_list()
    out[0]["payload"]["x"] = 99
    assert t.entries[0]["payload"]["x"] == 1


def test_events_of_filters_by_type():
    t = TelemetryKernel()
    t.record("step", {}); t.record("termination", {}); t.record("step", {})
    assert len(t.events_of("step")) == 2


def test_identical_sequences_hash_identically():
    a, b = TelemetryKernel(), TelemetryKernel()
    for t in (a, b):
        t.record("step", {"n": 1})
        t.record("termination", {"outcome": "success"})
    assert a.structural_hash() == b.structural_hash()
    assert a.content_hash() == b.content_hash()


def test_structural_hash_ignores_payload_values():
    a, b = TelemetryKernel(), TelemetryKernel()
    a.record("step", {"n": 1})
    b.record("step", {"n": 2})
    assert a.structural_hash() == b.structural_hash()
    assert a.content_hash() != b.content_hash()


def test_event_order_changes_the_structural_hash():
    a, b = TelemetryKernel(), TelemetryKernel()
    a.record("step", {}); a.record("termination", {})
    b.record("termination", {}); b.record("step", {})
    assert a.structural_hash() != b.structural_hash()


def test_historical_alias_points_at_the_kernel():
    assert Telemetry is TelemetryKernel
