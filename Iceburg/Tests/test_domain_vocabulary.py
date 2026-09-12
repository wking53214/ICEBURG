"""Intent and Emotion: the fixed vocabularies snapshots are written against."""
from Build_Graph import build_graph
from CallerState import CallerState
from Emotion import Emotion
from Intent import Intent


def test_every_intent_has_a_journey():
    """Intent is load-bearing, not descriptive: Simulator._next_node() looks
    it up in the graph's journey map."""
    journeys = build_graph().journeys
    for value in Intent.values():
        assert value in journeys, value


def test_every_journey_has_a_named_intent():
    for intent in build_graph().journeys:
        assert Intent.is_known(intent), intent


def test_intents_are_json_safe():
    import json
    assert json.dumps({"intent": Intent.BILLING}) == '{"intent": "billing"}'


def test_emotions_are_json_safe():
    import json
    assert json.dumps({"e": Emotion.NEUTRAL}) == '{"e": "NEUTRAL"}'


def test_caller_state_default_emotion_is_in_the_vocabulary():
    assert CallerState.new("c0").emotion in Emotion.values()


def test_unknown_intent_is_reported_as_unknown():
    assert not Intent.is_known("teleportation")
